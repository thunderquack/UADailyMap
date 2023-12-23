import os
import subprocess
import tempfile
import shutil


repo_url = "https://github.com/owlmaps/UAControlMapBackups.git"
ok = False

with tempfile.TemporaryDirectory() as temp_dir:
    print("Временная папка создана:", temp_dir)
    try:
        subprocess.run(["git", "clone", repo_url, temp_dir], check=True)
        print("Репозиторий успешно клонирован.")
        folder_path = temp_dir

        all_files = [f for f in os.listdir(folder_path) if f.endswith('.kmz')]

        # Сортируем имена файлов
        sorted_files = sorted(all_files)

        # Берем файл с последней датой
        latest_file = os.path.join(folder_path, sorted_files[-1])
        shutil.copy(latest_file, '.')

        pre_latest_file = os.path.join(folder_path, sorted_files[-2])
        shutil.copy(pre_latest_file, '.')
        
        print(f"Файл {latest_file} был скопирован в текущую директорию.")
        print(f"Файл {pre_latest_file} был скопирован в текущую директорию.")
        ok = True

    except subprocess.CalledProcessError as e:
        print("Произошла ошибка при клонировании репозитория.")

if not ok:
    exit(999)