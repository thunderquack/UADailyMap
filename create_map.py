import os
import subprocess
import tempfile
import shutil
import zipfile
import pandas as pd
import fiona
import geopandas as gpd
import folium
import re
import glob
import urllib.parse
import requests
from io import StringIO
from folium.plugins import BeautifyIcon
from folium.features import DivIcon
from datetime import datetime

def calculate_opacity(date_str, weeks_limit):
    # Получаем текущую дату
    current_date = datetime.now()
    # Преобразуем date_str в объект datetime
    event_date = datetime.strptime(date_str, "%Y-%m-%d")
    # Рассчитываем разницу в неделях
    weeks_difference = (current_date - event_date).days / 7
    # Нормализуем значение прозрачности на основе weeks_limit
    opacity = 1 - (weeks_difference / weeks_limit * 0.8)
    # Обеспечиваем, чтобы прозрачность лежала в пределах от 0.2 до 1
    return max(0.1, min(1, opacity))


def get_latest_date(dataframe):
    """Возвращает последнюю дату в данных."""
    dates = dataframe['Name'].apply(extract_and_convert_date).unique()
    return max(dates)


def extract_and_convert_date(input_string):
    pattern = r'\[(\d{2}\/\d{2}\/\d{2})\]\s(Ua|Ru)\sPosition'
    match = re.search(pattern, input_string)

    if match:
        date_str = match.group(1)
        # Конвертируем дату в нужный формат
        date_obj = datetime.strptime(date_str, '%y/%m/%d')
        return date_obj.strftime('%Y-%m-%d')
    return None


def convert_urls_to_copy_buttons(text):
    pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    def replace_with_button(match):
        url = match.group(0)
        button_html = f"""<button onclick="navigator.clipboard.writeText('{url}')">Copy URL</button>"""
        return button_html

    return re.sub(pattern, replace_with_button, text)


def convert_urls_to_links(text):
    adjusted_pattern = r"Description: (.+<br>http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)<br>"
    
    # Поиск и извлечение соответствующей части текста с использованием отрегулированного шаблона
    adjusted_match = re.search(adjusted_pattern, text)
    text = adjusted_match.group(1) if adjusted_match else "No match found"

    # Находим все URL в тексте
    urls = re.findall(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)

    # Для каждого URL заменяем его на текстовое поле с этим URL
    for url in urls:
        #replacement = f'<div style="width:330px;"><input type="text" value="{url}" onclick="this.select();" style="width:100%; border: none;" readonly></div>'
        replacement = f'<div style="width:330px;"><a href="{url}" target="_blank">{url}</a></div>'
        text = text.replace(url, replacement)

    return text


def style_red(feature):
    return {
        'fillColor': '#ff0000',  # красный цвет для заливки
        'color': '#ff0000',  # красный цвет для границы
        'weight': 1,
        'opacity': 1
    }


def style_red_dashes(feature):
    return {
        'fillColor': '#ff0000',  # красный цвет для заливки
        'color': '#ff0000',  # красный цвет для границы
        'weight': 1,
        'opacity': 1,
        'dashArray': '5, 10',  # пунктирная линия: 5 пикселей толщиной, 10 пикселей разрыв
        'lineCap': 'round'  # закругленные концы линий
    }


def style_dark_red(feature):
    return {
        'fillColor': '#8B0000',  # тёмно-красный цвет для заливки
        'color': '#8B0000',  # тёмно-красный цвет для границы
        'weight': 1,
        'opacity': 1
    }


def style_lemon(feature):
    return {
        'fillColor': '#B0FF00',
        'color': '#B0FF00',
        'weight': 2,
        'fillOpacity': 0.7
    }


def style_dark_green(feature):
    return {
        'fillColor': '#006400',  # оранжевый
        'color': '#006400',     # оранжевый
        'weight': 2,
        'opacity': 0.7,
        'fillOpacity': 0.7,
    }


def style_yellow(feature):
    return {
        'fillColor': '#FFFF00',
        'color': '#FFFF00',
        'weight': 2,
        'fillOpacity': 0.2
    }


def add_marker(row, map_obj, weeks_limit, latest_date, color):
    x, y, _ = row['geometry'].coords[0]
    date_str = extract_and_convert_date(row['Name'])
    if date_str == latest_date:
        icon_square = BeautifyIcon(
            icon_shape='circle-dot',
            border_color=color,
            border_width=4,
        )
        folium.Marker(
            show=False,
            location=[y, x],
            icon=icon_square,
            popup='<b>'+date_str + '</b> ' +
            convert_urls_to_links(row['Description'])
        ).add_to(map_obj)
        return
    icon_circle = BeautifyIcon(
        icon_shape='rectangle-dot',
        border_color=color,
        border_width=4,
    )
    folium.Marker(
        show=False,
        location=[y, x],
        icon=icon_circle,
        opacity=calculate_opacity(date_str, weeks_limit),
        popup='<b>'+date_str + '</b> ' +
        convert_urls_to_links(row['Description'])
    ).add_to(map_obj)


def display_geo_data(gf, map_obj, weeks_limit, latest_day):
    for idx, row in gf.iterrows():
        style_function = globals().get(row['fill'], None)
        if row['geometry'].geom_type == 'Polygon':
            folium.GeoJson(row['geometry'],
                           style_function=style_function, name=row['Name']).add_to(map_obj)
        elif row['geometry'].geom_type in ['LineString', 'MultiLineString']:
            folium.GeoJson(row['geometry'],
                           style_function=style_function, name=row['Name']).add_to(map_obj)
        elif row['geometry'].geom_type == 'Point':
            if row['code'].upper() == 'RU':
                add_marker(row, map_obj, weeks_limit, latest_day, 'red')
            else:
                add_marker(row, map_obj, weeks_limit, latest_day, 'blue')
    return map_obj

def display_today_data(today_data, map_obj):
    for idx, row in today_data.iterrows():
        try:
            x = row['Latitude']
            y = row['Longitude']
            text = row[column_name_text]
            link = row[column_name_link]
            if row[column_name_flag].upper()=='RU':
                color = 'red'
            else:
                color = 'blue'
            custom_icon = DivIcon(
                icon_size=(10,10),  # Устанавливаем размер иконки
                icon_anchor=(8,8),  # Центрируем иконку
                html='<div style="width: 10px; height: 10px; border: 3px solid {color}; '
                     'border-radius: 50%; background: transparent;"></div>'.format(color=color)
            )
            folium.Marker(
                show=False,
                location=[x, y],
                icon=custom_icon,
                popup='<b>'+ today + '</b> ' + text + '<br>' + f'<div style="width:330px;"><a href="{link}" target="_blank">{link}</a></div>'            
            ).add_to(map_obj)
        except:
            print(f'Warning, {row} is not added')

    return map_obj


repo_url = "https://github.com/owlmaps/UAControlMapBackups.git"
doc_id = '1u0N-CJNyuB4oSRwHpPkI27bAzwjCfBbAPUH4DKO7gqY'
page_name = 'Logs 2023'
csv_url = f'https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(page_name)}'

ok = False

temp_dir = tempfile.TemporaryDirectory()
#temp_dir = 'tmp'

print("Временная папка создана:", temp_dir)
try:
    if type(temp_dir) == str:
        folder_path = temp_dir
        if not os.path.exists(temp_dir):
            subprocess.run(["git", "clone", "--depth", "1", repo_url, temp_dir], check=True)
    else:
        subprocess.run(["git", "clone", repo_url, temp_dir.name], check=True)
        folder_path = temp_dir.name
    print("Репозиторий успешно клонирован.")    
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

if not temp_dir=='tmp':
    temp_dir.cleanup()

if not ok:
    exit(999)

add_today = False
response = requests.get(csv_url)

if response.status_code == 200:
    add_today = True
    # Преобразуйте текст ответа в CSV
    operative_data = pd.read_csv(StringIO(response.text))
    column_name_date = operative_data.columns.to_list()[0]
    column_name_event = operative_data.columns.to_list()[3]
    column_name_flag = operative_data.columns.to_list()[4]
    column_name_text = operative_data.columns.to_list()[5]
    column_name_link = operative_data.columns.to_list()[6]
    # Выведите первые строки DataFrame для проверки
    selected_columns = [
        column_name_date,  # Date column
        column_name_event,  # Event column
        column_name_flag,  # Flag column
        column_name_text,  # Text column
        column_name_link   # Link column
    ]
    operative_data = operative_data[selected_columns]
    today = datetime.now().strftime('%d/%m')
    operative_data = operative_data[operative_data[column_name_date] == today]
    # Удаление строк, где есть пустые поля или поля с whitespace
    operative_data.replace('', pd.NA, inplace=True)  # Заменяем пустые строки на NA для последующего удаления
    operative_data.replace(r'^\s*$', pd.NA, regex=True, inplace=True)  # Заменяем строки только с whitespace на NA
    operative_data.dropna(how='any', inplace=True)  # Удаляем строки с NA значениями
    if operative_data.shape[0]!=0:
        # Для колонки Flag заменим любые значения, содержащие "Ru" на "RU" и "Ua" на "UA"
        operative_data[column_name_flag] = operative_data[column_name_flag].str.replace(r'.*Ru.*', 'RU', regex=True)
        operative_data[column_name_flag] = operative_data[column_name_flag].str.replace(r'.*Ua.*', 'UA', regex=True)
        coordinate_columns = operative_data[column_name_event].str.split(', ', n=1, expand=True)
        if coordinate_columns.shape[1] == 2:
            coordinate_columns.columns = ['Latitude', 'Longitude']
            operative_data = pd.concat([operative_data, coordinate_columns], axis=1)
            operative_data['Delete'] = False
        else:
            operative_data['Delete'] = True
        operative_data = operative_data[operative_data['Delete'] != True]
        operative_data.drop(columns=['Delete'], errors='ignore', inplace=True)
        # Удалим старую колонку Event, теперь, когда у нас есть отдельные колонки для широты и долготы
        operative_data.drop(column_name_event, axis=1, inplace=True)

    # Теперь operative_data содержит только нужные колонки и строки без пустых значений
    operative_data.reset_index(drop=True, inplace=True)  # Сбросим индекс для красоты

else:
    print("Ошибка при загрузке данных: Статус", response.status_code)

driver = 'KML'

fiona.drvsupport.supported_drivers[driver] = 'rw'
#fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

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
for layer in fiona.listlayers(temp_filepath, driver=driver):
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
for layer in fiona.listlayers(temp_filepath, driver=driver):
    gdf_layer = gpd.read_file(temp_filepath, layer=layer)
    pre_all_layers.append(gdf_layer)

pre_frontline = pre_all_layers[0]

pre_frontline['Name'] = "Frontline -1"

temp_dir.cleanup()

# Количество недель
weeks_limit = 1

# Регулярное выражение для позиции
pattern = r'\[(\d{2}\/\d{2}\/\d{2})\]\s(Ua|Ru)\sPosition'

# Фильтрация строк
matches = gdf['Name'].str.extract(pattern)

# Извлекаем даты и преобразуем их в формат datetime
matches[0] = pd.to_datetime(matches[0], format='%y/%m/%d')

gdf['date'] = matches[0]
gdf['code'] = matches[1]

# Устанавливаем диапазон дат
end_date = pd.Timestamp.now()
start_date = end_date - pd.Timedelta(weeks=weeks_limit)

# Фильтруем датасет на основе дат и наличия соответствий
last_week_gf = gdf[matches[0]
                   .between(start_date, end_date)
                   & matches[1].notnull()].copy()

# Запомнить последнюю дату
latest_date = get_latest_date(last_week_gf)

gf = gdf[0:1].copy()  # frontline
gf['fill'] = 'style_red'
# 1, 4, 5 : луганск, херсон, донецк - направления, возможно пригодятся

pre_frontline['fill'] = 'style_red_dashes'
gf = pd.concat([gf, pre_frontline], ignore_index=True)

occupied = gdf[1:2].copy()
occupied['fill'] = 'style_red'
gf = pd.concat([gf, occupied], ignore_index=True)

occupied = gdf[4:6].copy()
occupied['fill'] = 'style_red'
gf = pd.concat([gf, occupied], ignore_index=True)

ldnr = gdf[2:3].copy()
ldnr['fill'] = 'style_dark_red'
gf = pd.concat([gf, ldnr], ignore_index=True)

crimea = gdf[3:4].copy()
crimea['fill'] = 'style_dark_red'
gf = pd.concat([gf, crimea], ignore_index=True)

fortifications = gdf[gdf['Name'] == 'Fortifications'].copy()
fortifications['fill'] = 'style_lemon'
gf = pd.concat([gf, fortifications], ignore_index=True)

dragon_teeth = gdf[gdf['Name'] == 'Dragon Teeth'].copy()
dragon_teeth['fill'] = 'style_dark_green'
gf = pd.concat([gf, dragon_teeth], ignore_index=True)

# offensive = gdf[14:15].copy()
# offensive['fill'] = 'style_yellow'
# gf = pd.concat([gf, offensive], ignore_index=True)


gf = pd.concat([gf, last_week_gf], ignore_index=True)

m = folium.Map(tiles=None, zoom_start=5, location=[50, 37], control_scale=True)

# Добавляем ваши геоданные
display_geo_data(gf, m, weeks_limit, latest_date)

today = datetime.now().strftime('%Y-%m-%d')


if add_today:
    display_today_data(operative_data, m)

# Добавляем тайлы google
folium.TileLayer(
    tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    attr="Google satellite",
    name="Google satellite"
).add_to(m)

# Добавляем тайлы OpenTopoMap
folium.TileLayer(
    tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    attr="© OpenTopoMap contributors, © OpenStreetMap contributors",
    name='OpenTopoMap'
).add_to(m)

# Добавляем контроллер для переключения тайлов
folium.LayerControl().add_to(m)

html = m.get_root().render()
index_file = os.path.join('docs', 'index.html')
with open(index_file, 'w', encoding='utf-8') as file:
    file.write(html)
for kmz_file in glob.glob('*.kmz'):
    os.remove(kmz_file)
