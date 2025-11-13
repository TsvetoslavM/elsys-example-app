import io
import random
from locust import HttpUser, task, between


class FileApiUser(HttpUser):
	wait_time = between(0.5, 1.5)

	@task(3)
	def health(self):
		self.client.get("/health", name="GET /health")

	@task(2)
	def list_files(self):
		self.client.get("/files", name="GET /files")

	@task(2)
	def metrics(self):
		self.client.get("/metrics", name="GET /metrics")

	@task(1)
	def upload_file(self):
		# Small random file content
		filename = f"file_{random.randint(1, 100000)}.txt"
		content = f"payload-{random.randint(1, 1_000_000)}".encode()
		files = {"file": (filename, io.BytesIO(content), "text/plain")}
		self.client.post("/files", files=files, name="POST /files")


