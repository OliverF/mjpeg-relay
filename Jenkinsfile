pipeline{

	agent any

	environment {
		DOCKERHUB_CREDENTIALS=credentials("dockerhub-credential")
	}

	stages {

		stage('Build') {
			steps {
				sh 'docker build -t hdavid0510/mjpeg-relay:latest .'
			}
		}

		stage('Login') {
			steps {
				sh 'echo $DOCKERHUB_CREDENTIALS_PSW | docker login -u $DOCKERHUB_CREDENTIALS_USR --password-stdin'
			}
		}

		stage('Push') {
			steps {
				sh 'docker push hdavid0510/mjpeg-relay:latest'
			}
		}
	}

	post {
		always {
			sh 'docker logout'
		}
	}

}
