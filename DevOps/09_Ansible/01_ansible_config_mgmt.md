# Ansible — Configuration Management
**DevOps Track · Phase 9: Ansible**

## Quick Concepts

- **Ansible** = agentless configuration management / automation tool — runs over SSH, no daemon needed on target hosts
- **Inventory** = the list of hosts (and groups of hosts) Ansible manages
- **Playbook** = a YAML file describing a sequence of tasks to run against hosts
- **Task** = a single action (install a package, copy a file, restart a service)
- **Module** = the unit of work a task calls (`apt`, `copy`, `service`, `template`, hundreds built in)
- **Handler** = a task that only runs when notified by another task, typically for restarts
- **Role** = a standardized directory structure packaging tasks/handlers/templates/vars for reuse
- **Idempotency** = running the same playbook twice produces the same end state, second run reports "no changes"
- **Jinja2** = the templating engine Ansible uses for variables and config file templates
- **Vault** = Ansible's built-in mechanism for encrypting secrets inside version-controlled files
- **Galaxy** = Ansible's public role/collection registry (like npm/PyPI, but for reusable automation)
- **Ad-hoc command** = a one-off module run directly from the CLI (`ansible web -m ping`), no playbook needed
- **`register`** = captures a task's full result object into a variable, usable by later tasks/conditionals

---

## Why This Matters — Where Ansible Fits Next to Terraform

```
Terraform answers: "what infrastructure EXISTS?"     (provisioning)
Ansible answers:    "what STATE is that infrastructure in?"  (configuration)

Terraform creates the EC2 instance.
Ansible installs nginx on it, drops the right config file, opens the
right file permissions, starts the service, and keeps it that way.

Neither tool is a full replacement for the other — the standard pairing
in a real pipeline is: Terraform provisions → Ansible configures →
(often) a CI/CD pipeline deploys application code on top of both.
```

Because Ansible is agentless (SSH + Python on the target, nothing to install and maintain as a background daemon like Puppet/Chef require), it has one of the lowest adoption-cost profiles of any config management tool — which is exactly why it shows up so often in mid-size shops that don't want to run a separate management infrastructure just to manage their infrastructure.

---

## `ansible.cfg` — Project-Level Configuration

Before touching inventory or playbooks — the config file every real Ansible project has, so nobody has to type `-i inventory.yml` and a dozen other flags on every single command.

```ini
# ansible.cfg (in the project root — Ansible auto-discovers it there)
[defaults]
inventory = ./inventory.yml
remote_user = deploy
host_key_checking = False
roles_path = ./roles
retry_files_enabled = False

[privilege_escalation]
become = True
become_method = sudo
```

```
host_key_checking = False   → skips SSH's "authenticity of host can't be
                                established, are you sure you want to
                                continue connecting?" prompt — the #1
                                reason a FIRST-EVER ansible run against a
                                new host hangs forever in CI (no human
                                there to type "yes"). Fine for disposable/
                                ephemeral infra; for long-lived hosts, the
                                more correct fix is pre-populating known_hosts.

inventory = ./inventory.yml   → means every command below can drop
                                -i inventory.yml entirely, since this
                                config already points at it
```

```bash
ansible-config view              # see the fully resolved config
ansible-config dump --only-changed   # see ONLY settings that differ from defaults —
                                        # useful for "what did someone actually change here"
```

---

## Inventory

### Static Inventory — INI Format

```ini
# inventory.ini
[web]
web1.example.com
web2.example.com

[db]
db1.example.com ansible_user=dbadmin

[web:vars]
http_port=8080

[all:vars]
ansible_user=deploy
ansible_ssh_private_key_file=~/.ssh/prod_key
```

### Static Inventory — YAML Format

```yaml
# inventory.yml
all:
  vars:
    ansible_user: deploy
    ansible_ssh_private_key_file: ~/.ssh/prod_key
  children:
    web:
      hosts:
        web1.example.com:
        web2.example.com:
      vars:
        http_port: 8080
    db:
      hosts:
        db1.example.com:
          ansible_user: dbadmin
```

```bash
ansible-inventory -i inventory.yml --graph      # visualize group structure
ansible web -i inventory.yml -m ping            # test connectivity to the 'web' group
```

### Dynamic Inventory

```
Static inventory doesn't scale once hosts come and go via Auto Scaling
Groups, or when the "list of servers" genuinely lives in AWS/GCP/Azure
rather than a file you maintain by hand.

A dynamic inventory is a script (or the built-in aws_ec2 plugin) that
QUERIES the cloud provider's API at run time and builds the host list
on the fly — tagged by instance tags, region, VPC, etc., instead of
being hand-maintained.
```

```yaml
# inventory_aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions:
  - ap-south-1
filters:
  tag:Environment: production
  instance-state-name: running
keyed_groups:
  - key: tags.Role
    prefix: role
```

```bash
ansible-inventory -i inventory_aws_ec2.yml --graph
ansible role_web -i inventory_aws_ec2.yml -m ping
```

With this, an ASG scaling from 3 to 8 instances means the NEXT playbook run automatically targets all 8 — nobody edits an inventory file by hand when instances launch or terminate. This is the practical reason dynamic inventory is close to mandatory once Auto Scaling Groups are in the picture.

---

## Ad-Hoc Commands — Before You Need a Whole Playbook

For a genuine one-off ("is this package installed on every host RIGHT NOW," "restart this service everywhere") a full playbook is overkill — an ad-hoc command runs ONE module against a target group directly from the CLI.

```bash
ansible web -m ping                                  # connectivity + Python interpreter check
ansible web -m setup                                   # dump ALL gathered facts for these hosts
ansible web -m command -a "df -h"                        # run a command, see output from every host
ansible web -m shell -a "systemctl status nginx | grep Active"   # needs shell features (pipes) — see below
ansible web -m copy -a "src=./app.conf dest=/etc/app.conf"          # copy a file, one-off
ansible web -m service -a "name=nginx state=restarted" --become       # restart a service everywhere
ansible db -m user -a "name=readonly_user state=absent" --become        # remove a user, one-off cleanup
ansible all -m package -a "name=htop state=present" --become --limit web1.example.com  # scope to ONE host
```

### `command` vs `shell` vs `raw` — A Genuinely Common Interview Question

```
command  → runs a command directly, NOT through a shell — no pipes (|),
           redirects (>), environment variable expansion ($HOME), or
           globbing (*). Safer (no shell-injection surface), and the
           DEFAULT/preferred choice whenever you don't specifically
           need shell features.

shell    → runs the command through /bin/sh — pipes, redirects, env
           vars, globbing all work, same as typing it in a terminal.
           Use ONLY when you genuinely need a shell feature; reaching
           for shell out of habit when command would do is a common
           code-review flag (it's both a security surface and usually
           a sign a dedicated module — copy/template/lineinfile — would
           have been more idempotent anyway).

raw      → bypasses Ansible's module system ENTIRELY, sends the exact
           string over SSH with no Python required on the target at
           all. The ONLY module that works against a target with no
           Python interpreter installed — mainly useful for the very
           FIRST task ever run against a fresh/minimal host (e.g.
           bootstrapping Python itself so every subsequent module can
           work normally).
```

```yaml
# The one legitimate reason to reach for raw in a real playbook —
# bootstrapping Python on a minimal image BEFORE any other module can run
- name: Bootstrap Python on a bare-minimum host
  ansible.builtin.raw: apt-get update && apt-get install -y python3
  changed_when: false
```

---

## Playbooks — Tasks, Handlers, Notify

```yaml
# site.yml
---
- name: Configure web servers
  hosts: web
  become: true
  vars:
    app_port: 8000

  tasks:
    - name: Install nginx
      ansible.builtin.apt:
        name: nginx
        state: present
        update_cache: true

    - name: Deploy nginx site config
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-available/app.conf
        owner: root
        group: root
        mode: "0644"
      notify: Reload nginx

    - name: Enable the site
      ansible.builtin.file:
        src: /etc/nginx/sites-available/app.conf
        dest: /etc/nginx/sites-enabled/app.conf
        state: link
      notify: Reload nginx

    - name: Ensure nginx is running and enabled at boot
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

```
become: true       → run tasks with privilege escalation (sudo), the
                     Ansible equivalent of prefixing every shell command
                     with sudo, but scoped and auditable per-task

notify: <handler>  → a task that CHANGES something notifies a handler;
                     the handler runs ONCE at the end of the play, even
                     if multiple tasks notify it — this is why config
                     template changes trigger a reload but ONLY when
                     something actually changed, not on every run

state: present / started / enabled
                   → declarative, not imperative — "make sure nginx
                     package is present" not "run apt install nginx".
                     Running this playbook 10 times in a row produces
                     the same end state every time (idempotency) —
                     runs after the first report "0 changed" because
                     there's nothing left to do
```

```bash
ansible-playbook -i inventory.yml site.yml
ansible-playbook -i inventory.yml site.yml --check    # dry run, no changes applied
ansible-playbook -i inventory.yml site.yml --diff     # show what WOULD change
ansible-playbook -i inventory.yml site.yml --limit web1.example.com   # target one host
```

---

## Everyday Task Constructs — `loop`, `when`, `register`, `tags`

The single playbook shown above has no loops or conditionals — here's what real task lists actually look like.

### `loop` — Repeating a Task Over a List

```yaml
- name: Install several packages
  ansible.builtin.apt:
    name: "{{ item }}"
    state: present
  loop:
    - nginx
    - curl
    - htop

- name: Create multiple app users
  ansible.builtin.user:
    name: "{{ item.name }}"
    groups: "{{ item.groups }}"
  loop:
    - { name: "alice", groups: "sudo" }
    - { name: "deploy", groups: "www-data" }
```

```
Older playbooks use with_items instead of loop — functionally similar,
loop is the current recommended form (more consistent lookup syntax
across different iteration sources). You'll see both in the wild;
write NEW playbooks with loop.
```

### `when` — Conditional Task Execution

```yaml
- name: Install nginx (Debian/Ubuntu)
  ansible.builtin.apt:
    name: nginx
    state: present
  when: ansible_os_family == "Debian"

- name: Install nginx (RHEL/CentOS)
  ansible.builtin.yum:
    name: nginx
    state: present
  when: ansible_os_family == "RedHat"

- name: Only restart if config actually changed
  ansible.builtin.service:
    name: nginx
    state: restarted
  when: nginx_config.changed     # references a REGISTERED result — see below
```

```
ansible_os_family, ansible_distribution, ansible_fqdn — all FACTS,
automatically gathered per-host before the play runs (same facts the
Jinja2 template section above referenced). `when` is how a SINGLE
playbook targets a mixed fleet (some Ubuntu, some RHEL) without
branching into separate playbooks per OS.
```

### `register` and `debug` — Capturing and Inspecting Task Output

```yaml
- name: Check if a config file exists
  ansible.builtin.stat:
    path: /etc/app/config.yml
  register: config_check

- name: Show what we found
  ansible.builtin.debug:
    var: config_check.stat.exists

- name: Only run this if the file was missing
  ansible.builtin.copy:
    src: default-config.yml
    dest: /etc/app/config.yml
  when: not config_check.stat.exists

- name: Deploy config, capture whether it actually changed
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  register: nginx_config

- name: Restart only if the template changed anything
  ansible.builtin.service:
    name: nginx
    state: restarted
  when: nginx_config.changed
```

```
register captures a task's FULL result object (not just success/fail)
into a variable — .changed, .stdout, .rc (exit code), .stat (for the
stat module) are all available afterward. debug is the module for
actually PRINTING a variable's value mid-playbook-run, the closest
thing Ansible has to a print statement for troubleshooting a playbook
that isn't doing what you expect.
```

### Tags — Running Only Part of a Playbook

```yaml
tasks:
  - name: Install nginx
    ansible.builtin.apt:
      name: nginx
      state: present
    tags: [install]

  - name: Deploy config
    ansible.builtin.template:
      src: nginx.conf.j2
      dest: /etc/nginx/nginx.conf
    tags: [config]

  - name: Run integration tests
    ansible.builtin.command: /opt/scripts/smoke_test.sh
    tags: [test, never]    # 'never' — SKIPPED unless explicitly requested
```

```bash
ansible-playbook site.yml --tags config          # run ONLY tasks tagged "config"
ansible-playbook site.yml --skip-tags test          # run everything EXCEPT "test"-tagged tasks
ansible-playbook site.yml --tags test                 # 'never' tag means this only runs
                                                         # when EXPLICITLY requested by name
```

```
Real use: a full playbook installs + configures + runs smoke tests,
but a quick "I just changed the config template, don't reinstall the
package" iteration during development is --tags config — seconds
instead of a full re-run across every task.
```

---

## Roles — Standardized Reuse

A role is Ansible's answer to "this set of tasks/templates/vars keeps getting copy-pasted between playbooks" — a fixed directory convention that Ansible auto-discovers, so you stop wiring things together manually.

```bash
ansible-galaxy init roles/nginx    # scaffolds the structure below
```

```
roles/
└── nginx/
    ├── tasks/
    │   └── main.yml          # the task list (like the tasks: block above)
    ├── handlers/
    │   └── main.yml          # handlers (like the handlers: block above)
    ├── templates/
    │   └── nginx.conf.j2     # Jinja2 templates this role deploys
    ├── files/
    │   └── (static files copied as-is, no templating)
    ├── vars/
    │   └── main.yml          # role-internal variables, high precedence
    ├── defaults/
    │   └── main.yml          # role's DEFAULT variable values, lowest precedence
    │                           (meant to be overridden by the caller)
    ├── meta/
    │   └── main.yml          # role metadata + dependencies on other roles
    └── README.md
```

```yaml
# roles/nginx/defaults/main.yml
nginx_worker_connections: 1024
nginx_listen_port: 80
```

```yaml
# roles/nginx/tasks/main.yml
---
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present

- name: Deploy config from template
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: Reload nginx
```

```yaml
# roles/nginx/handlers/main.yml
---
- name: Reload nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded
```

Using the role from a playbook:

```yaml
# site.yml
---
- name: Configure web servers
  hosts: web
  become: true
  roles:
    - role: nginx
      vars:
        nginx_listen_port: 8080
```

`defaults/main.yml` values are the lowest-precedence variable source specifically so that any caller of the role can override them without editing the role itself — that's what makes a role portable across projects/teams instead of needing a fork per consumer.

---

## Templates — Jinja2

```nginx
# roles/nginx/templates/nginx.conf.j2
server {
    listen {{ nginx_listen_port }};
    server_name {{ ansible_fqdn | default('_') }};

    location / {
        proxy_pass http://127.0.0.1:{{ app_port }};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

{% if enable_health_check | default(true) %}
    location /health {
        access_log off;
        return 200 "ok\n";
    }
{% endif %}

{% for upstream in backend_servers %}
    # backend: {{ upstream.name }} -> {{ upstream.ip }}:{{ upstream.port }}
{% endfor %}
}
```

```
{{ variable }}          → substitution
{% if ... %} {% endif %} → conditional blocks
{% for ... %} {% endfor %} → loops
| default('_')           → Jinja2 filter, fallback if the variable is undefined
ansible_fqdn              → a FACT — automatically gathered from the target
                             host by Ansible before the play runs (hostname,
                             OS, IP addresses, CPU count, etc. — inspect the
                             full list with `ansible web -m setup`)
```

Rendering this template with `nginx_listen_port: 8080`, `app_port: 8000`, and a `backend_servers` list produces a real, valid `nginx.conf` — the same template renders differently per host/group depending on the variables in scope for that host, which is the whole value proposition over hand-copying static config files.

---

## Variables — Precedence Order (the Common Interview Gotcha)

This is one of the most-asked Ansible interview questions because the answer genuinely surprises people who've only used roles casually. From **lowest to highest** precedence (higher overrides lower):

```
 1. role defaults                        (roles/x/defaults/main.yml)
 2. inventory file/group vars             ([group:vars] in INI, or group_vars/)
 3. inventory group_vars/all
 4. playbook group_vars/all
 5. inventory group_vars/<group>
 6. playbook group_vars/<group>
 7. inventory host_vars/<hostname>
 8. playbook host_vars/<hostname>
 9. host facts / cached set_facts
10. play vars (vars: block in the playbook)
11. play vars_prompt
12. play vars_files
13. role vars                             (roles/x/vars/main.yml)
14. block vars
15. task vars
16. include_vars
17. set_facts / registered vars
18. role (and include_role) params
19. include params
20. extra vars                            (-e on the command line)  ← ALWAYS WINS
```

The two ends of this list are what actually matter in practice:

```
role defaults    → LOWEST precedence, by design — they exist purely
                    as sane fallbacks meant to be overridden

extra vars (-e)   → HIGHEST precedence, ALWAYS — nothing in any file
                    can out-rank a value passed with -e on the CLI,
                    which is exactly why -e is used for one-off
                    overrides and CI/CD pipeline parameterization:

                    ansible-playbook site.yml -e "nginx_listen_port=9090"

                    This will win even if nginx_listen_port is also
                    set in vars/main.yml, group_vars, host_vars — ALL
                    of it. This surprises people who set a value in
                    what looks like a "more specific" file and can't
                    figure out why -e still overrides it.
```

**The interview-safe summary**: "role defaults are the floor, command-line extra-vars are the ceiling, and everything else stacks in between roughly from least-specific (inventory-wide) to most-specific (task-level), with the mental model being: more specific and more explicit generally wins, except role internal `vars/` deliberately outranks the caller's `group_vars`/`host_vars` too — which is why you override role behavior via `defaults`, not by fighting a role's `vars/main.yml` from outside."

---

## Vault — Encrypting Secrets

```
Playbooks and variable files live in git. Database passwords, API
keys, and TLS private keys cannot live in git in plaintext. Vault
solves this by encrypting the VALUE (or the whole file) at rest,
decryptable only with a password/key supplied at run time.
```

```bash
# Create a new encrypted file
ansible-vault create group_vars/prod/vault.yml
# opens $EDITOR, you type plaintext, it's saved encrypted

# Encrypt an existing plaintext file
ansible-vault encrypt group_vars/prod/secrets.yml

# Edit an encrypted file in place
ansible-vault edit group_vars/prod/vault.yml

# View without editing
ansible-vault view group_vars/prod/vault.yml

# Decrypt permanently (rarely what you want in a shared repo)
ansible-vault decrypt group_vars/prod/vault.yml

# Encrypt a single string inline in a normal YAML file
ansible-vault encrypt_string 'S3cretP@ss' --name 'db_password'
```

```yaml
# group_vars/prod/vault.yml (contents after decryption, for illustration)
vault_db_password: "S3cretP@ss"
vault_api_key: "sk_live_abcdef123456"
```

```yaml
# group_vars/prod/vars.yml (plaintext, references the vaulted values)
db_password: "{{ vault_db_password }}"
api_key: "{{ vault_api_key }}"
```

The `vars.yml` / `vault.yml` split (a common convention, not a hard requirement) keeps plaintext variable NAMES readable/greppable in the repo while the actual secret VALUES stay encrypted — you can see that `db_password` exists and what references it, without the encrypted file leaking anything if someone greps the repo.

```bash
# Running a playbook that needs vault-decrypted vars
ansible-playbook site.yml --ask-vault-pass
# or, non-interactively (CI/CD), point at a password file (never commit this file)
ansible-playbook site.yml --vault-password-file ~/.vault_pass.txt
```

---

## Galaxy — Using Community Roles

```bash
# Install a role from Ansible Galaxy
ansible-galaxy install geerlingguy.nginx

# Or, the modern preferred approach: a requirements file
```

```yaml
# requirements.yml
roles:
  - name: geerlingguy.postgresql
    version: "3.4.0"

collections:
  - name: amazon.aws
    version: ">=7.0.0"
  - name: community.general
```

```bash
ansible-galaxy install -r requirements.yml
```

```
Roles       → the reusable "playbook building block" unit, same
              directory structure covered above, published by the
              community (geerlingguy's roles are a widely-used example)
Collections → a broader packaging format bundling roles, modules,
              plugins together (e.g. amazon.aws bundles all the AWS-
              specific modules like ec2_instance, s3_bucket, etc.)
```

Pinning exact versions in `requirements.yml` (not just "latest") and committing that file is the same discipline as pinning a `package.json`/`requirements.txt` — an unpinned community role updating underneath you is a real, if under-discussed, source of "the playbook that worked last month suddenly fails."

---

## End-to-End Example — Install and Configure Nginx on a Group of Hosts

```yaml
# inventory.yml
all:
  vars:
    ansible_user: deploy
  children:
    web:
      hosts:
        web1.example.com:
        web2.example.com:
        web3.example.com:
```

```yaml
# group_vars/web.yml
app_port: 8000
nginx_listen_port: 80
enable_health_check: true
```

```yaml
# roles/nginx/defaults/main.yml
nginx_listen_port: 80
enable_health_check: true
```

```yaml
# roles/nginx/tasks/main.yml
---
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present
    update_cache: true

- name: Remove default site
  ansible.builtin.file:
    path: /etc/nginx/sites-enabled/default
    state: absent
  notify: Reload nginx

- name: Deploy app site config from template
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/sites-available/app.conf
    owner: root
    group: root
    mode: "0644"
  notify: Reload nginx

- name: Enable app site
  ansible.builtin.file:
    src: /etc/nginx/sites-available/app.conf
    dest: /etc/nginx/sites-enabled/app.conf
    state: link
  notify: Reload nginx

- name: Ensure nginx is started and enabled
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true
```

```yaml
# roles/nginx/handlers/main.yml
---
- name: Reload nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded
```

```nginx
# roles/nginx/templates/nginx.conf.j2
server {
    listen {{ nginx_listen_port }};
    server_name {{ inventory_hostname }};

    location / {
        proxy_pass http://127.0.0.1:{{ app_port }};
        proxy_set_header Host $host;
    }

{% if enable_health_check %}
    location /health {
        access_log off;
        return 200 "ok\n";
    }
{% endif %}
}
```

```yaml
# site.yml
---
- name: Install and configure nginx on all web hosts
  hosts: web
  become: true
  roles:
    - nginx
```

```bash
# Dry run first — always
ansible-playbook -i inventory.yml site.yml --check --diff

# Real run
ansible-playbook -i inventory.yml site.yml

# Verify idempotency — run again immediately, expect "0 changed"
ansible-playbook -i inventory.yml site.yml
```

Running this against 3 hosts installs nginx, removes the distro default site, renders a per-host config from the template (using `inventory_hostname` so each host's config correctly names itself), enables the new site, and starts/reloads the service — the same playbook works unchanged whether `web` has 3 hosts or 30, static inventory or dynamic AWS inventory.

---

## Senior Tip

```
Always run --check --diff before a real apply on production hosts —
same discipline as `terraform plan` before `apply`. It's the difference
between finding out a template has a typo BEFORE nginx fails to reload
across your entire fleet, versus finding out during an outage.

And always verify idempotency by running a playbook TWICE in dev — if
the second run reports anything other than "0 changed, 0 failed" for
tasks that shouldn't have drifted, something in the playbook isn't
truly declarative (a shell/command task doing something raw `apt` or
`template` modules would have done idempotently) — that's worth fixing
before it reaches production, where re-runs are common (re-converging
drifted config, or CI re-running a playbook on every deploy).
```

## Interview Angle

**Q: You need to override a role's default `nginx_listen_port` for exactly one CI/CD pipeline run, without touching any committed files. How?**

`ansible-playbook site.yml -e "nginx_listen_port=9090"` — extra-vars (`-e`) sit at the very top of the precedence chain, above role defaults, group_vars, host_vars, and role-internal vars, specifically so CLI-level one-off overrides always win without needing to edit any tracked file. This is the standard mechanism CI/CD pipelines use to parameterize a shared playbook per run (image tag, target port, feature flag) without maintaining separate variable files per pipeline invocation.

**Q: What's the actual difference between the `command`, `shell`, and `raw` modules, and when would you use each?**
`command` runs directly, no shell involved — no pipes, redirects, or env var expansion, and the default/safest choice. `shell` runs through `/bin/sh`, so pipes/redirects/globbing all work, but it's a larger surface area and usually a sign a dedicated module (copy/template/lineinfile) would be more idempotent — reach for it only when you genuinely need a shell feature. `raw` bypasses Ansible's module system entirely and sends the literal command over SSH with no Python required on the target — the only module that works against a host with no Python installed at all, mainly used to bootstrap Python itself on a fresh minimal image before any other module can run.

**Q: You need to restart nginx only when its config template actually changed, not on every playbook run. How do you express that?**
Register the template task's result (`register: nginx_config`), then gate the restart task with `when: nginx_config.changed`. This is functionally similar to what a `notify`/handler pair already does automatically for a single change-triggers-restart relationship, but `register`+`when` gives you the same idea with arbitrary conditional logic — useful when the restart depends on more than just "did this one task change something."

**Q: A playbook installs, configures, AND runs a slow integration test suite every single run — but during active development you only want to re-apply the config template. How do you avoid re-running everything?**
Tag each logical section of the playbook (`tags: [install]`, `tags: [config]`, `tags: [test]`), then run `ansible-playbook site.yml --tags config` to execute only the config-related tasks. `--skip-tags` does the inverse (run everything except a given tag), and a `never` tag on the slow test suite means it's skipped by default unless explicitly requested by name.

---

## Related

- [../08_Terraform/01_terraform_iac.md](../08_Terraform/01_terraform_iac.md) — Terraform provisions the hosts this file configures
- [../07_Cloud_AWS/01_iam_compute_ec2.md](../07_Cloud_AWS/01_iam_compute_ec2.md) — EC2 instances as Ansible's dynamic inventory targets
- [../13_Web_Servers/](../13_Web_Servers/) — deeper nginx configuration beyond this proxy example
- [../10_CICD/](../10_CICD/) — wiring `ansible-playbook` runs into a CI/CD pipeline
