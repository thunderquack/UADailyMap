import os
import subprocess

repo_url = "https://github.com/owlmaps/UAControlMapBackups.git"

os.chdir('docs')

try:
    subprocess.run(["git", "clone", repo_url], check=True)
    print("Репозиторий успешно клонирован.")
except subprocess.CalledProcessError as e:
    print("Произошла ошибка при клонировании репозитория.")