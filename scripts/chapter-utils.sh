#!/bin/bash

# Утилиты для работы с именами папок глав (с префиксами и без)

# Извлекает chapter_id из имени папки
# Если папка имеет формат "001.chapter_id", возвращает "chapter_id"
# Если папка имеет формат "chapter_id", возвращает "chapter_id"
extract_chapter_id() {
    local folder_name="$1"
    # Убираем префикс вида "001." если он есть
    if [[ "$folder_name" =~ ^[0-9]{3}\.(.+)$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "$folder_name"
    fi
}

# Получает путь к папке главы по chapter_id
# Ищет папку с префиксом или без него
get_chapter_dir() {
    local chapter_id="$1"
    local chapters_dir="$2"
    
    # Сначала ищем папку с префиксом (формат: 001.chapter_id)
    for dir in "$chapters_dir"/[0-9][0-9][0-9]."$chapter_id"; do
        if [ -d "$dir" ]; then
            echo "$dir"
            return 0
        fi
    done
    
    # Если не найдено, ищем без префикса
    if [ -d "$chapters_dir/$chapter_id" ]; then
        echo "$chapters_dir/$chapter_id"
        return 0
    fi
    
    # Не найдено
    return 1
}

# Получает имя папки главы по chapter_id из generation-status.json
get_chapter_folder_name() {
    local chapter_id="$1"
    local status_file="$2"
    
    if [ ! -f "$status_file" ]; then
        return 1
    fi
    
    # Извлекаем output_dir из status файла
    local output_dir=$(jq -r --arg id "$chapter_id" '.chapters[] | select(.chapter_id == $id) | .output_dir' "$status_file" 2>/dev/null)
    
    if [ -n "$output_dir" ] && [ "$output_dir" != "null" ]; then
        # Извлекаем имя папки из пути "chapters/001.chapter_id"
        basename "$output_dir"
    else
        return 1
    fi
}
