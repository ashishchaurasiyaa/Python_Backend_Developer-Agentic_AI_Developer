# CI/CD — Jenkins
**DevOps Track · Phase 10: CI/CD**

## Quick Concepts

- **CI (Continuous Integration)** = every commit is built + tested automatically
- **CD (Continuous Delivery/Deployment)** = every passing build is automatically deployable / auto-deployed
- **Jenkins** = self-hosted, open-source automation server — the original CI/CD tool, still dominant in enterprises with on-prem or regulated infra
- **Controller (master)** = the Jenkins brain — schedules jobs, serves UI, stores config; does NOT run builds itself in a healthy setup
- **Agent (node/slave)** = a machine (VM, container, bare metal) that actually executes build steps
- **Executor** = a slot on an agent that can run one build at a time
- **Pipeline** = a job defined as code (`Jenkinsfile`), either Declarative or Scripted
- **Stage** = a logical phase of a pipeline (Build, Test, Deploy) — shown as a block in the Jenkins UI
- **Shared Library** = reusable Groovy code shared across multiple Jenkinsfiles/repos
- **Webhook** = HTTP callback from GitHub/GitLab that triggers a Jenkins build the moment code is pushed
- **Credentials Store** = Jenkins' encrypted vault for secrets (SSH keys, tokens, passwords) referenced by ID in pipelines, never hardcoded
- **`input`** = a manual approval gate — pauses the pipeline until a human explicitly approves
- **`parallel`** = runs multiple sub-stages simultaneously instead of sequentially, cutting wall-clock pipeline time

---

## Why This Matters

```
GitHub Actions is great for GitHub-hosted, cloud-native projects.
Jenkins still runs the CI/CD for:
   - Large enterprises with on-prem GitLab/Bitbucket/SVN
   - Regulated industries (banking, healthcare) that can't use SaaS CI
   - Complex multi-team pipelines needing custom plugins
   - Legacy systems predating GitHub Actions (2019+)

If you interview at a mid-size or enterprise company (not a startup
born on GitHub), there is a real chance their pipeline is Jenkins.
Knowing "declarative pipeline, agents, shared libraries, credentials"
signals you've worked in a non-trivial CI/CD setup, not just clicked
through GitHub's wizard.
```

---

## Installation (Docker — Fastest Path)

You do not need to compile Jenkins from source or fight with `apt` repos. For local practice and most modern deployments, Docker is standard:

```bash
docker run -d --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts

# Get the initial admin password
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

Then open `http://localhost:8080`, paste the password, install "Suggested Plugins" (Git, Pipeline, Credentials Binding are the essentials), and create your first admin user.

For production, Jenkins usually runs as a Deployment in Kubernetes (via the official Helm chart) or as a systemd service on a dedicated VM — the controller must survive restarts, so `JENKINS_HOME` (job configs, build history, credentials) always lives on persistent storage.

---

## Architecture: Controller / Agent Model

```
                    ┌─────────────────────┐
                    │   Jenkins Controller  │
                    │  (schedules jobs,     │
                    │   serves UI, stores    │
                    │   config + creds)      │
                    └──────────┬───────────┘
                               │ (JNLP / SSH)
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │  Agent (VM)    │   │ Agent (Docker) │   │ Agent (K8s pod) │
   │  static, always │   │ dynamic, spun  │   │ dynamic, spun   │
   │  online          │   │ up per build   │   │ up per build    │
   └───────────────┘   └───────────────┘   └───────────────┘
```

### Static Agents

- Provisioned once, stay online permanently (a dedicated VM registered to Jenkins)
- Good for: agents needing heavy pre-installed toolchains (licensed software, huge SDKs), or environments where spin-up cost is high
- Downside: idle cost, drift over time (someone SSHs in and installs something), harder to guarantee reproducibility

### Dynamic Agents (Cloud Agents)

- Spun up on-demand per build (Docker container or Kubernetes pod), destroyed after
- Configured via the **Docker plugin** or the **Kubernetes plugin** (agents run as ephemeral pods with a defined pod template — image, resource limits, volumes)
- Preferred in modern setups: clean environment every build, no drift, scales to zero when idle

```groovy
// Example: Kubernetes plugin agent defined inline in a Jenkinsfile
pipeline {
    agent {
        kubernetes {
            yaml '''
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: python
                    image: python:3.12-slim
                    command: ["cat"]
                    tty: true
            '''
        }
    }
    stages {
        stage('Test') {
            steps {
                container('python') {
                    sh 'pip install -r requirements.txt && pytest'
                }
            }
        }
    }
}
```

---

## Pipelines: Declarative vs Scripted

| | Declarative | Scripted |
|---|---|---|
| Syntax | Structured, opinionated (`pipeline { stages { ... } }`) | Full Groovy, imperative (`node { stage(...) { ... } }`) |
| Learning curve | Lower — reads like config | Higher — need Groovy knowledge |
| Flexibility | Constrained (by design) | Unlimited — loops, custom functions, complex logic |
| Validation | Built-in linting, better error messages | Errors often surface at runtime |
| When to use | 90% of pipelines — CI/CD for a service | Complex orchestration, dynamic stage generation |

### Declarative Pipeline — Real Example

```groovy
// Jenkinsfile
pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = 'myregistry.example.com'
        IMAGE_NAME       = 'backend-api'
        // Credentials injected from Jenkins credentials store
        DOCKERHUB_CREDS  = credentials('dockerhub-creds')
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        githubPush()          // build on every push (via webhook)
        cron('H 2 * * *')     // also run nightly, staggered hash-based
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'pip install -r requirements.txt'
            }
        }

        stage('Test') {
            steps {
                sh 'pytest --junitxml=results.xml'
            }
            post {
                always {
                    junit 'results.xml'
                }
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} ."
            }
        }

        stage('Push Image') {
            when {
                branch 'main'
            }
            steps {
                sh """
                    echo \$DOCKERHUB_CREDS_PSW | docker login -u \$DOCKERHUB_CREDS_USR --password-stdin ${DOCKER_REGISTRY}
                    docker push ${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER}
                """
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                sh 'kubectl set image deployment/backend-api backend-api=${DOCKER_REGISTRY}/${IMAGE_NAME}:${BUILD_NUMBER} -n prod'
            }
        }
    }

    post {
        failure {
            slackSend channel: '#deploys', color: 'danger',
                      message: "Build ${env.BUILD_NUMBER} FAILED: ${env.BUILD_URL}"
        }
        success {
            slackSend channel: '#deploys', color: 'good',
                      message: "Build ${env.BUILD_NUMBER} deployed to prod"
        }
    }
}
```

### Scripted Pipeline — Same Idea, Imperative Style

```groovy
node {
    stage('Checkout') {
        checkout scm
    }
    stage('Build') {
        sh 'pip install -r requirements.txt'
    }
    stage('Test') {
        try {
            sh 'pytest --junitxml=results.xml'
        } finally {
            junit 'results.xml'
        }
    }
    if (env.BRANCH_NAME == 'main') {
        stage('Deploy') {
            sh 'kubectl apply -f k8s/'
        }
    }
}
```

Scripted gives you `if`/`try`/`for` at the top level naturally — useful when stage list itself is dynamic (e.g., generate a stage per microservice found in a monorepo).

---

## Pipeline Syntax You'll Actually Need Constantly

The Declarative example above shows the core shape. These four constructs show up in almost every real pipeline and aren't in it yet.

### Parameters — Configurable Builds

```groovy
pipeline {
    agent any
    parameters {
        choice(name: 'ENVIRONMENT', choices: ['staging', 'production'], description: 'Deploy target')
        string(name: 'VERSION', defaultValue: 'latest', description: 'Image tag to deploy')
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Skip the test stage')
    }
    stages {
        stage('Test') {
            when { expression { !params.SKIP_TESTS } }
            steps { sh 'pytest' }
        }
        stage('Deploy') {
            steps {
                sh "kubectl set image deployment/api api=myrepo/api:${params.VERSION} -n ${params.ENVIRONMENT}"
            }
        }
    }
}
```

```
Triggering with parameters via "Build with Parameters" in the UI (or
the Jenkins CLI / a webhook payload mapping fields to params) is how
the SAME pipeline definition serves "deploy staging" and "deploy
production" without maintaining two separate Jenkinsfiles.
```

### Parallel Stages — Running Independent Work Concurrently

```groovy
stage('Test') {
    parallel {
        stage('Unit Tests') {
            steps { sh 'pytest tests/unit' }
        }
        stage('Lint') {
            steps { sh 'ruff check .' }
        }
        stage('Security Scan') {
            steps { sh 'trivy fs .' }
        }
    }
}
```

```
These three sub-stages run SIMULTANEOUSLY (each needs its own
executor/agent slot) instead of sequentially — cuts wall-clock pipeline
time significantly when steps are genuinely independent. If any one
fails, the whole `parallel` block is marked failed, but the others
still run to completion by default (useful for seeing ALL failures at
once, not just the first one encountered).
```

### `input` — A Manual Approval Gate Before Production

```groovy
stage('Approve Production Deploy') {
    steps {
        input message: 'Deploy this build to production?',
              ok: 'Deploy',
              submitter: 'release-managers'
    }
}
stage('Deploy to Production') {
    steps {
        sh 'kubectl apply -f k8s/production/'
    }
}
```

```
The pipeline PAUSES at the input step — indefinitely, no timeout by
default — until a human with the required permission (submitter:
restricts WHO can approve) clicks "Deploy" in the Jenkins UI. This is
the standard Jenkins mechanism for "code passed every automated check,
but a human still explicitly approves the production push" — add a
timeout() option wrapping it in real pipelines so a forgotten approval
doesn't hold an agent executor hostage indefinitely.
```

### Post Conditions Beyond Success/Failure

```groovy
post {
    always {
        junit 'results.xml'                    // runs EVERY time, regardless of outcome
    }
    success {
        echo 'Build succeeded'
    }
    failure {
        slackSend message: "Build failed: ${env.BUILD_URL}"
    }
    unstable {
        echo 'Build succeeded but tests reported failures (non-zero test failures, build not marked FAILED)'
    }
    changed {
        echo 'This build's status is DIFFERENT from the previous run'   // e.g. was
                                                                          // failing, now passing —
                                                                          // useful for "recovered"
                                                                          // notifications distinct
                                                                          // from every-run noise
    }
    aborted {
        echo 'Build was manually cancelled or timed out'
    }
}
```

---

## Shared Libraries

**Why**: once you have 10+ Jenkinsfiles across repos, you end up copy-pasting the same "build docker image", "notify slack", "deploy to k8s" logic everywhere. A change (e.g., new registry) means editing 10 files. Shared Libraries centralize that logic into one versioned Groovy repo that every Jenkinsfile imports.

**When**: adopt once you have more than a handful of pipelines with repeated logic, or once security/platform teams want to enforce standard steps (e.g., mandatory vulnerability scan stage) across all teams.

### Structure

```
(shared-library-repo)
├── vars/
│   ├── buildDockerImage.groovy    # global function: buildDockerImage(...)
│   └── deployToK8s.groovy
├── src/
│   └── com/mycompany/Utils.groovy # reusable Groovy classes
└── resources/
    └── templates/deployment.yaml
```

```groovy
// vars/buildDockerImage.groovy
def call(String imageName, String tag) {
    sh "docker build -t ${imageName}:${tag} ."
    sh "docker push ${imageName}:${tag}"
}
```

```groovy
// Jenkinsfile in any project repo — configured under
// Manage Jenkins > System > Global Pipeline Libraries
@Library('my-shared-library') _

pipeline {
    agent any
    stages {
        stage('Build & Push') {
            steps {
                buildDockerImage('myregistry.com/backend-api', env.BUILD_NUMBER)
            }
        }
    }
}
```

---

## Credentials

Jenkins never wants secrets typed into a Jenkinsfile in plaintext — the file is version-controlled and readable by anyone with repo access. Instead:

1. **Manage Jenkins → Credentials → Add Credentials** — store the secret (username/password, SSH key, secret text, or a certificate) encrypted at rest, tagged with an **ID** (e.g., `dockerhub-creds`, `prod-ssh-key`).
2. Reference the ID in the pipeline — Jenkins injects the value into the build environment only for the duration of that step, and masks it in console logs.

```groovy
pipeline {
    agent any
    stages {
        stage('Deploy') {
            steps {
                // Username/Password credential -> two env vars: _USR and _PSW
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh 'echo $DOCKER_PASS | docker login -u $DOCKER_USER --password-stdin'
                }

                // SSH key credential
                withCredentials([sshUserPrivateKey(
                    credentialsId: 'prod-ssh-key',
                    keyFileVariable: 'SSH_KEY'
                )]) {
                    sh 'ssh -i $SSH_KEY deploy@prod.example.com "systemctl restart myapp"'
                }
            }
        }
    }
}
```

Credentials can be scoped **global** (any job) or **folder-level** (restricted to a team's jobs) — folder scoping is how multi-team Jenkins instances keep one team from reading another's prod secrets.

---

## Webhooks — Triggering Builds from GitHub

Polling GitHub every N minutes ("SCM polling") is slow and wasteful. The standard is a webhook: GitHub pushes an event to Jenkins the instant something happens.

**Setup:**

1. In GitHub repo → **Settings → Webhooks → Add webhook**
   - Payload URL: `https://jenkins.example.com/github-webhook/`
   - Content type: `application/json`
   - Events: "Just the push event" (or add Pull Request events too)
2. In Jenkins job → check **"GitHub hook trigger for GITScm polling"**, or declaratively:

```groovy
pipeline {
    agent any
    triggers {
        githubPush()
    }
    stages { /* ... */ }
}
```

3. Jenkins must be reachable from GitHub's servers — for local Jenkins behind NAT, use `ngrok` or a reverse-tunnel during development; in production, Jenkins sits behind a proper public URL/load balancer.

**Multibranch Pipeline** is the common companion: Jenkins auto-discovers every branch and PR in a repo and creates/destroys a pipeline job for each, driven by the webhook — this is how "build runs automatically on every PR" works without manually creating a job per branch.

---

## Senior Tip

```
Jenkins failure modes that separate juniors from seniors:

1. Controller running builds directly (agent: any with no real
   agents configured) → one bad build can crash the whole controller.
   Always offload execution to agents.

2. Credentials hardcoded in Jenkinsfile "temporarily" → they're now
   in git history forever. Rotate immediately, use credentials store.

3. No `disableConcurrentBuilds()` on deploy pipelines → two pushes in
   quick succession race to deploy, second one wins non-deterministically.

4. Static agents that nobody patches → become the least-audited,
   most-compromised box in the network. Prefer ephemeral agents.

5. Groovy sandbox errors ("script not yet approved") → Jenkins
   sandboxes Scripted pipelines and unusual Groovy calls for security;
   an admin must approve new method signatures under
   Manage Jenkins > In-process Script Approval.
```

## Interview Angle

**Q: "Jenkins vs GitHub Actions — when would you pick Jenkins for a new project?"**
Rarely for a brand-new, GitHub-hosted project — GitHub Actions has less operational overhead (no controller to patch/scale, native integration). Jenkins wins when: you need on-prem/air-gapped execution, you have deep custom plugin requirements GitHub Actions can't match, or you're integrating heterogeneous non-GitHub systems (SVN, internal artifact servers, legacy Windows build agents) into one pipeline.

**Q: "How do you keep 50 Jenkinsfiles in sync when a step changes?"**
Shared Library — extract common steps into `vars/*.groovy`, version it, and every pipeline pulls the same logic via `@Library`.

**Q: "How do you add a manual approval step before a production deploy, and what's the operational risk of doing it naively?"**
The `input` step pauses the pipeline until a human clicks approve, optionally restricted to specific users/groups via `submitter:`. The risk: `input` has no timeout by default — a forgotten or delayed approval holds that pipeline's agent executor (and on some setups, blocks that executor from other work) indefinitely. Real pipelines wrap it in a `timeout()` option so an abandoned approval eventually fails cleanly instead of silently hanging forever.

**Q: "Three independent test suites take 5 minutes each sequentially — how do you cut that down without reducing test coverage?"**
A `parallel` block running each suite as its own sub-stage — since they don't depend on each other, they can execute simultaneously (each needing its own executor), cutting wall-clock time toward the length of the SLOWEST suite rather than the sum of all three. The tradeoff is needing enough available executors/agents to actually run them concurrently, not just declaring them parallel.

---

## Related

- [`02_github_actions.md`](02_github_actions.md) — the same CI/CD concepts (matrix builds ≈ parallel stages, environments ≈ input approval gates) in GitHub's native tooling
- [`../14_Security/03_iam_vuln_scanning.md`](../14_Security/03_iam_vuln_scanning.md) — the Trivy/SBOM scanning steps that fit naturally into a `parallel` test stage above
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — what the "Deploy to Production" stage should actually do (canary/rolling, not a single big-bang `kubectl apply`)
