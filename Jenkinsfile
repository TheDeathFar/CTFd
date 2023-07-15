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

                    sh '''#!/bin/bash

                    DOCKER_SOCKET=/var/run/docker.sock
                    DOCKER_GROUP=docker

                    if [ -S ${DOCKER_SOCKET} ]; then
                      DOCKER_GID=$(stat -c '%g' ${DOCKER_SOCKET})
                      groupadd -for -g ${DOCKER_GID} ${DOCKER_GROUP}
                      usermod -aG ${DOCKER_GROUP} ${JENKINS_USER}
                    fi
                    '''
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
