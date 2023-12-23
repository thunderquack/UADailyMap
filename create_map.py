import os
import subprocess
import tempfile
import shutil
import zipfile
import pandas as pd
import fiona
import geopandas as gpd


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
        latest_file = os.path.basename(latest_file)

        pre_latest_file = os.path.join(folder_path, sorted_files[-2])
        shutil.copy(pre_latest_file, '.')
        pre_latest_file = os.path.basename(pre_latest_file)
        
        print(f"Файл {latest_file} был скопирован в текущую директорию.")
        print(f"Файл {pre_latest_file} был скопирован в текущую директорию.")
        ok = True

    except subprocess.CalledProcessError as e:
        print("Произошла ошибка при клонировании репозитория.")

if not ok:
    exit(999)

fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
# Создание временного файла
temp_dir = tempfile.TemporaryDirectory()
temp_filepath = os.path.join(temp_dir.name, 'temp_kml.kml')

# Распаковка KMZ во временный файл
with zipfile.ZipFile(latest_file, 'r') as zip_ref:
    kml_filename = zip_ref.namelist()[0]
    zip_ref.extract(kml_filename, temp_dir.name)
    os.rename(os.path.join(temp_dir.name, kml_filename), temp_filepath)

# Чтение KML из временного файла с помощью geopandas
all_layers = []
for layer in fiona.listlayers(temp_filepath, driver="KML"):
    gdf_layer = gpd.read_file(temp_filepath, layer=layer)
    all_layers.append(gdf_layer)

# Объединение всех слоев в один GeoDataFrame
gdf = pd.concat(all_layers, ignore_index=True)

# Очистка и удаление временного файла и директории
temp_dir.cleanup()

# Создание временного файла
temp_dir = tempfile.TemporaryDirectory()
temp_filepath = os.path.join(temp_dir.name, 'temp_kml.kml')

# Распаковка KMZ во временный файл
with zipfile.ZipFile(pre_latest_file, 'r') as zip_ref:
    kml_filename = zip_ref.namelist()[0]
    zip_ref.extract(kml_filename, temp_dir.name)
    os.rename(os.path.join(temp_dir.name, kml_filename), temp_filepath)

# Чтение KML из временного файла с помощью geopandas
pre_all_layers = []
for layer in fiona.listlayers(temp_filepath, driver="KML"):
    gdf_layer = gpd.read_file(temp_filepath, layer=layer)
    pre_all_layers.append(gdf_layer)

pre_frontline = pre_all_layers[0]

pre_frontline['Name'] = "Frontline -1"