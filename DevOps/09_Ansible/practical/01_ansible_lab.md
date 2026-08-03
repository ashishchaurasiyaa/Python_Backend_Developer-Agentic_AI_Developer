# Ansible — Hands-On Lab
**DevOps Track · Phase 9 Practical**

## Prerequisites

- Ansible installed on your control machine (`pip install ansible` or `brew install ansible`) — verify with `ansible --version`
- Target hosts to manage. You do **not** need real cloud VMs to practice most of this — free options:
  - **Docker containers** running an SSH-enabled base image (fastest, zero cost) — e.g. `geerlingguy/docker-ubuntu2204-ansible` images are built for exactly this
  - **Multipass** or **Vagrant** for lightweight local VMs if you want something closer to a real host
  - 2-3 AWS EC2 `t3.micro` free-tier instances if you want to practice against "real" cloud targets and try dynamic inventory later
- SSH key pair for connecting to targets (`ssh-keygen -t ed25519`)
- Basic YAML familiarity — if playbook indentation errors confuse you, that's normal at first; Ansible's error messages usually point at the exact line

This lab uses Docker containers as the simplest zero-cost path. Substitute real hosts/IPs anywhere `inventory.yml` appears if you're using VMs or EC2 instead.

```bash
# Spin up 2 lightweight SSH-enabled containers to act as your "web" group
docker run -d --name web1 -p 2221:22 geerlingguy/docker-ubuntu2204-ansible:latest
docker run -d --name web2 -p 2222:22 geerlingguy/docker-ubuntu2204-ansible:latest
```

---

## Lab 1: Inventory and Ad-Hoc Commands

**Objective:** Build a working inventory and prove connectivity before writing a single playbook — this is the "hello world" every real Ansible session starts with.

**Task:**
1. Create `inventory.yml` with a `web` group containing `web1` and `web2`, each reachable via SSH on their mapped ports, using `ansible_user=root` (the geerlingguy images default to root) or your VM's user.
2. Run `ansible-inventory -i inventory.yml --graph` and confirm the group structure looks right.
3. Run `ansible web -i inventory.yml -m ping` and confirm both hosts respond `pong`.
4. Use an ad-hoc command (no playbook) to check disk usage on both hosts: `ansible web -i inventory.yml -a "df -h"`.
5. Use an ad-hoc command with the `apt` module to install `curl` on just `web1` (not the whole group) using `--limit`.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# inventory.yml
all:
  vars:
    ansible_user: root
  children:
    web:
      hosts:
        web1:
          ansible_host: 127.0.0.1
          ansible_port: 2221
        web2:
          ansible_host: 127.0.0.1
          ansible_port: 2222
```

```bash
ansible-inventory -i inventory.yml --graph
# @all:
#   |--@web:
#   |  |--web1
#   |  |--web2

ansible web -i inventory.yml -m ping
# web1 | SUCCESS => { "changed": false, "ping": "pong" }
# web2 | SUCCESS => { "changed": false, "ping": "pong" }

ansible web -i inventory.yml -a "df -h"

ansible web -i inventory.yml --limit web1 -m apt -a "name=curl state=present update_cache=true" --become
```

**Why this matters:** `ping` doesn't check network reachability, it checks that Ansible can actually authenticate and run its Python-based module machinery on the target — a much stronger signal than raw `ssh` working. `--limit` is how you scope any playbook or ad-hoc run to a subset of an inventory group without maintaining a separate inventory file per subset.
</details>

---

## Lab 2: A Real Playbook — Install and Configure Nginx, Verify Idempotency

**Objective:** Write the exact playbook pattern from the lesson file — tasks, a Jinja2 template, a handler triggered by `notify` — and prove it's truly idempotent by running it twice.

**Task:**
1. Create `site.yml` targeting the `web` group with `become: true`.
2. Add tasks: install `nginx` (apt module), deploy a templated site config to `/etc/nginx/sites-available/app.conf`, symlink it into `sites-enabled`, and ensure the service is started and enabled.
3. The template (`templates/nginx.conf.j2`) should listen on a variable port (`app_port`, default `8080`) and proxy to `http://127.0.0.1:9000` (a placeholder backend — it doesn't need to actually exist for this lab).
4. Wire up a handler `Reload nginx` and make the template-deploy and symlink tasks `notify` it.
5. Run with `--check --diff` first (dry run) and read the diff output before doing a real run.
6. Run for real: `ansible-playbook -i inventory.yml site.yml`.
7. Run it again immediately, unchanged. Confirm the play recap shows `changed=0` for every task — that's proof of idempotency.
8. Change `app_port` via `-e` on the command line and re-run — confirm only the template/reload tasks report `changed`, nothing else.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# site.yml
---
- name: Configure web servers
  hosts: web
  become: true
  vars:
    app_port: 8080

  tasks:
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

```nginx
# templates/nginx.conf.j2
server {
    listen {{ app_port }};
    server_name {{ inventory_hostname }};

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
    }
}
```

```bash
ansible-playbook -i inventory.yml site.yml --check --diff   # dry run — read this before applying anything real
ansible-playbook -i inventory.yml site.yml                   # real run

ansible-playbook -i inventory.yml site.yml                   # run #2 — expect 0 changed
# PLAY RECAP
# web1 : ok=5  changed=0  unreachable=0  failed=0

ansible-playbook -i inventory.yml site.yml -e "app_port=9090"
# only "Deploy app site config" (template diff) and the "Reload nginx" handler show changed=1
```

**Why the second run matters more than the first:** anyone can write a playbook that works once. The `changed=0` on re-run is what proves it's declarative ("ensure this is the state") rather than imperative ("do this thing again"), which is the entire idempotency guarantee the lesson file's Senior Tip calls out as a real production concern — playbooks re-run constantly (drift correction, CI/CD redeploys), and a non-idempotent task means every re-run risks side effects.
</details>

---

## Lab 3: Refactor Into a Role + Variable Precedence Exercise

**Objective:** Package Lab 2 into a proper role with `defaults/`, and deliberately exercise the precedence chain the lesson file calls "the common interview gotcha."

**Task:**
1. Scaffold a role: `ansible-galaxy init roles/nginx`.
2. Move the tasks, handlers, and template from Lab 2 into the role's standard directories.
3. Set `nginx_listen_port: 80` and `enable_health_check: true` in `roles/nginx/defaults/main.yml` — these are the "floor" values, meant to be overridden.
4. Rewrite `site.yml` to use `roles: [nginx]` instead of inline tasks.
5. Create `group_vars/web.yml` setting `nginx_listen_port: 8080` — confirm this overrides the role default.
6. Now override AGAIN with `-e "nginx_listen_port=9090"` on the command line and confirm extra-vars wins over BOTH the role default and group_vars, without editing any tracked file.
7. As a deliberate gotcha, add `nginx_listen_port: 7000` to `roles/nginx/vars/main.yml` too (role-internal vars, high precedence) and re-run without `-e` — confirm role `vars/` beats `group_vars` even though `group_vars` "feels" more specific. Explain in a comment why this surprises people.
8. Encrypt a fake secret with `ansible-vault` (e.g. a placeholder API key) into `group_vars/web/vault.yml`, reference it from `group_vars/web/vars.yml`, and run the playbook with `--ask-vault-pass`.

<details>
<summary>Solution / walkthrough</summary>

```bash
ansible-galaxy init roles/nginx
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

- name: Deploy config from template
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/sites-available/app.conf
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

```yaml
# site.yml
---
- name: Configure web servers
  hosts: web
  become: true
  roles:
    - nginx
```

```yaml
# group_vars/web.yml
nginx_listen_port: 8080
```

```bash
ansible-playbook -i inventory.yml site.yml --diff
# listen 8080 — group_vars overrode the role default of 80

ansible-playbook -i inventory.yml site.yml -e "nginx_listen_port=9090" --diff
# listen 9090 — extra-vars ALWAYS wins, top of the precedence chain
```

**The deliberate gotcha:**
```yaml
# roles/nginx/vars/main.yml  (role-internal vars — NOT defaults)
nginx_listen_port: 7000
```
```bash
ansible-playbook -i inventory.yml site.yml --diff
# listen 7000 — NOT 8080, even though group_vars/web.yml "looks" like it should be more specific
```

This is exactly the surprise the lesson file flags: `roles/x/vars/main.yml` sits far above `group_vars`/`host_vars` in the precedence order, so a role author's internal `vars/` can silently defeat a caller's `group_vars` override. The fix, if you actually wanted `group_vars` to win, is to never put an overridable setting in `vars/` — put it in `defaults/` instead. This is why the lesson's rule of thumb is "override role behavior via `defaults`, not by fighting `vars/main.yml` from outside" — you can't win that fight from outside the role.

**Vault:**
```bash
ansible-vault create group_vars/web/vault.yml
# opens $EDITOR — type: vault_api_key: "sk_test_fake_1234567890"
```
```yaml
# group_vars/web/vars.yml (plaintext, references the vaulted value)
api_key: "{{ vault_api_key }}"
```
```bash
ansible-playbook -i inventory.yml site.yml --ask-vault-pass
```
</details>

---

## Lab 4: Troubleshooting — Fixing a Non-Idempotent Task

**Objective:** Debug the most common real-world Ansible code smell: a `shell`/`command` task standing in for a proper module, breaking idempotency.

**Task:**
1. Add this deliberately broken task to your playbook/role and run the playbook twice:
   ```yaml
   - name: Add a marker line to a config file
     ansible.builtin.shell: echo "managed_by_ansible=true" >> /etc/nginx/nginx.conf
   ```
2. Observe that it reports `changed=1` on EVERY run, not just the first — that's the tell.
3. Fix it using `ansible.builtin.lineinfile` instead, which is declarative ("ensure this line exists") rather than imperative ("append this text").
4. Re-run twice and confirm the second run reports `changed=0`.
5. Bonus: find and explain one more common idempotency trap — a `command: mkdir /some/dir` task — and fix it the declarative way.

<details>
<summary>Solution / walkthrough</summary>

**Broken (non-idempotent):**
```yaml
- name: Add a marker line to a config file
  ansible.builtin.shell: echo "managed_by_ansible=true" >> /etc/nginx/nginx.conf
```
Every run appends another copy of the line — `changed=1` forever, and the file grows unboundedly on every playbook run. `shell`/`command` modules have no concept of "already done"; they just execute the given command every single time.

**Fixed (declarative, idempotent):**
```yaml
- name: Ensure marker line exists in config file
  ansible.builtin.lineinfile:
    path: /etc/nginx/nginx.conf
    line: "managed_by_ansible=true"
    state: present
```
`lineinfile` checks whether the line already exists before doing anything — first run: `changed=1` (line added). Second run: `changed=0` (line already present, nothing to do).

**Bonus — the `mkdir` trap:**
```yaml
# Broken — fails outright on the second run instead of just misreporting
- name: Create app directory
  ansible.builtin.command: mkdir /opt/myapp

# Fixed
- name: Ensure app directory exists
  ansible.builtin.file:
    path: /opt/myapp
    state: directory
    mode: "0755"
```
`command: mkdir` actually errors on re-run (`mkdir: cannot create directory: File exists`) unless you add `creates: /opt/myapp` as a guard — but `ansible.builtin.file` with `state: directory` is idempotent by design and needs no guard at all. **Rule of thumb**: reach for a purpose-built module (`file`, `lineinfile`, `copy`, `template`, `apt`, `service`...) before falling back to `shell`/`command` — the built-in modules exist specifically so you don't have to hand-roll idempotency checks yourself.
</details>

---

## Self-Check Checklist

- [ ] Can you write a YAML inventory with a group, host-level `ansible_host`/`ansible_port` overrides, and group-level vars, from memory?
- [ ] Can you explain what `ansible -m ping` actually verifies, beyond basic SSH reachability?
- [ ] Can you write a playbook task that `notify`s a handler, and explain why the handler only runs once even if three tasks notify it?
- [ ] Can you explain, in your own words, why running a playbook twice and getting `changed=0` the second time is a meaningful correctness signal, not just a nice-to-have?
- [ ] Can you scaffold a role's directory structure and correctly place a variable in `defaults/` vs `vars/`, knowing the precedence difference?
- [ ] Can you recite where `-e` (extra-vars) sits in the precedence chain, and why CI/CD pipelines rely on that?
- [ ] Can you spot a `shell`/`command` task that should be a proper module, and name the idempotent replacement?
- [ ] Can you encrypt a secret with `ansible-vault` and reference it from a plaintext vars file without ever committing the plaintext secret?
- [ ] Can you explain the practical difference between static and dynamic inventory, and when an Auto Scaling Group makes dynamic inventory close to mandatory?
- [ ] Can you explain, out loud, "Terraform provisions, Ansible configures" and where each tool's responsibility ends?
