from database.repositories import Repository

repo: Repository | None = None

def setup(repository: Repository):
    global repo
    repo = repository
