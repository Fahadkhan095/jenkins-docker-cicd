// Jenkinsfile — Declarative Pipeline
// Python project: install -> lint -> test -> build Docker image -> push to registry
//
// Prerequisites (see README.md for full setup):
//   - Jenkins plugins: Pipeline, Docker Pipeline, Git, JUnit, Credentials Binding
//   - A Jenkins agent with Docker installed and the Jenkins user in the "docker" group
//   - A Jenkins credential (Username/Password or Username/Token) storing your
//     registry login, referenced below as REGISTRY_CREDENTIALS_ID
//   - A Jenkins credential (Secret text or file) for anything else your app needs (DB URLs, etc.)

pipeline {
    agent any

    options {
        timestamps()
        // Keep the last 20 builds; discard the rest to save disk space
        buildDiscarder(logRotator(numToKeepStr: '20'))
        // Fail fast if a stage hangs (e.g. a stuck docker push)
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    parameters {
        // Lets you trigger a manual run against a different tag/branch if needed
        string(name: 'IMAGE_TAG_OVERRIDE', defaultValue: '', description: 'Optional: override the computed image tag')
    }

    environment {
        // --- Edit these three for your project ---
        REGISTRY            = 'registry.example.com'          // e.g. docker.io/yourorg, ghcr.io/yourorg, your ECR URL
        IMAGE_NAME           = 'my-python-app'
        REGISTRY_CREDENTIALS_ID = 'registry-creds'             // ID of the Jenkins credential for docker login
        // -------------------------------------------

        PYTHON_VERSION = '3.12'
        IMAGE_TAG      = "${params.IMAGE_TAG_OVERRIDE ?: env.GIT_COMMIT?.take(8) ?: env.BUILD_NUMBER}"
        FULL_IMAGE     = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                sh 'git rev-parse HEAD'
            }
        }

        stage('Set up Python') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pip install flake8
                    flake8 . --max-line-length=100 --exclude=.venv
                '''
            }
        }

        stage('Test') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pip install pytest pytest-cov
                    pytest --junitxml=reports/junit.xml --cov=. --cov-report=xml
                '''
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh "docker build -t ${FULL_IMAGE} ."
            }
        }

        stage('Scan image (optional)') {
            when { expression { return fileExists('/usr/local/bin/trivy') } }
            steps {
                sh "trivy image --exit-code 0 --severity HIGH,CRITICAL ${FULL_IMAGE} || true"
            }
        }

        stage('Push to registry') {
            when {
                // Only push from the main branch or tags — adjust to your branching model
                anyOf {
                    branch 'main'
                    buildingTag()
                }
            }
            steps {
                withCredentials([usernamePassword(
                    credentialsId: env.REGISTRY_CREDENTIALS_ID,
                    usernameVariable: 'REG_USER',
                    passwordVariable: 'REG_PASS'
                )]) {
                    sh '''
                        echo "$REG_PASS" | docker login ${REGISTRY} -u "$REG_USER" --password-stdin
                        docker push ${FULL_IMAGE}
                        docker logout ${REGISTRY}
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
            cleanWs()
        }
        success {
            echo "Build succeeded: ${FULL_IMAGE}"
        }
        failure {
            echo "Build failed — check the stage logs above."
        }
    }
}
