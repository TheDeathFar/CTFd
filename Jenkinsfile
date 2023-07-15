pipeline {
    environment {
        dockerimagename = 'deathfar/ctfd-app'
        dockerImage = ''
    }
    agent any
    stages {
        stage('Checkout Source') {
            steps {
                git 'https://github.com/TheDeathFar/CTFd'
            }
        }

        stage('Initialize') {
            steps {
                script {
                    def dockerHome = tool 'myDocker'
                    env.PATH = "${dockerHome}/bin:${env.PATH}"
                }
            }
        }

        stage('Build image') {
            steps {
                script {
                    dockerImage = docker.build dockerimagename
                }
            }
        }

        stage('Pushing Image') {
            environment {
                registryCredential = 'dockerhub-credentials'
            }
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', registryCredential) {
                        dockerImage.push('latest')
                    }
                }
            }
        }

        stage('Deploying container to Kubernetes') {
            steps {
                script {
                    kubernetesDeploy(configs: 'deployment.yaml', 'service.yaml', 'ingress.yaml')
                }
            }
        }
    }
}
