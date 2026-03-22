#!/bin/bash

# Скрипт для бесконечного запуска codex exec с паузой между запусками
# Использование: ./scripts/run-codex-loop.sh

# Цветовые коды ANSI
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GRAY='\033[0;90m'
BOLD='\033[1m'
RESET='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_FILE="$PROJECT_ROOT/prompts/0-master-prompt.md"
PAUSE_SECONDS=10
ITERATION=1

# Обработка Ctrl+C для корректного завершения
trap 'echo ""; echo -e "${RED}🛑 Остановка цикла...${RESET}"; exit 0' INT TERM

cd "$PROJECT_ROOT" || exit 1

# Функция для форматирования времени в дни, часы, минуты, секунды
format_time() {
    local total_seconds=$1
    local days=$((total_seconds / 86400))
    local hours=$(((total_seconds % 86400) / 3600))
    local minutes=$(((total_seconds % 3600) / 60))
    local seconds=$((total_seconds % 60))
    
    local result=""
    if [ $days -gt 0 ]; then
        result="${days} дн "
    fi
    if [ $hours -gt 0 ]; then
        result="${result}${hours} ч "
    fi
    if [ $minutes -gt 0 ]; then
        result="${result}${minutes} мин "
    fi
    # Всегда показываем секунды для стабильности формата
    result="${result}${seconds} сек"
    
    echo "$result"
}

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${CYAN}🔄 Запуск бесконечного цикла codex exec${RESET}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "${BLUE}Промпт:${RESET} ${GRAY}$PROMPT_FILE${RESET}"
echo -e "${BLUE}Пауза между запусками:${RESET} ${YELLOW}${PAUSE_SECONDS} секунд${RESET}"
echo -e "${GRAY}Для остановки нажмите Ctrl+C${RESET}"
echo ""

while true; do
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}${MAGENTA}🔄 Итерация #$ITERATION${RESET} ${GRAY}- $(date '+%Y-%m-%d %H:%M:%S')${RESET}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
    
    # Запуск codex exec с перехватом вывода для проверки на ошибку 429
    # Используем tee для одновременного вывода на экран и сохранения в переменную
    OUTPUT=$(codex exec --full-auto "run $PROMPT_FILE" 2>&1 | tee /dev/tty)
    EXIT_CODE=${PIPESTATUS[0]}
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Итерация #$ITERATION завершена успешно${RESET}"
    else
        echo -e "${YELLOW}⚠️  Итерация #$ITERATION завершена с кодом ошибки: ${RED}$EXIT_CODE${RESET}"
    fi
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
    
    # Проверка на ошибку 429 (лимит использования)
    if echo "$OUTPUT" | grep -qiE "(429|usage_limit_reached|usage limit has been reached)"; then
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
        echo -e "${BOLD}${RED}🛑 Обнаружена ошибка лимита использования (429)${RESET}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
        echo ""
        
        # Попытка извлечь время ожидания из JSON ответа
        WAIT_SECONDS=0
        
        # Пробуем извлечь resets_in_seconds
        # Ищем строку с resets_in_seconds и извлекаем все числа, берем последнее (обычно это значение после двоеточия)
        RESETS_LINE=$(echo "$OUTPUT" | grep -i "resets_in_seconds" | head -1)
        if [ -n "$RESETS_LINE" ]; then
            # Извлекаем все числа и берем последнее (это значение resets_in_seconds)
            # Обычно формат: "resets_in_seconds":1265, поэтому последнее число - это значение
            RESETS_IN_SECONDS=$(echo "$RESETS_LINE" | grep -oE '[0-9]+' | tail -1)
            # Отладочный вывод
            echo -e "${GRAY}   [DEBUG] Найдена строка: ${RESETS_LINE:0:100}...${RESET}" >&2
            echo -e "${GRAY}   [DEBUG] Извлечено resets_in_seconds: ${RESETS_IN_SECONDS}${RESET}" >&2
        fi
        
        if [ -n "$RESETS_IN_SECONDS" ] && [ "$RESETS_IN_SECONDS" -gt 0 ] 2>/dev/null; then
            WAIT_SECONDS=$RESETS_IN_SECONDS
        else
            # Пробуем извлечь resets_at и вычислить разницу
            RESETS_AT_LINE=$(echo "$OUTPUT" | grep -i "resets_at" | head -1)
            if [ -n "$RESETS_AT_LINE" ]; then
                RESETS_AT=$(echo "$RESETS_AT_LINE" | grep -oE '[0-9]+' | tail -1)
            fi
            
            if [ -n "$RESETS_AT" ] && [ "$RESETS_AT" -gt 0 ] 2>/dev/null; then
                CURRENT_TIME=$(date +%s)
                WAIT_SECONDS=$((RESETS_AT - CURRENT_TIME))
            fi
        fi
        
        # Если не удалось определить время, используем значение по умолчанию (5 минут)
        if [ -z "$WAIT_SECONDS" ] || [ "$WAIT_SECONDS" -le 0 ]; then
            echo -e "${YELLOW}⚠️  Не удалось определить время сброса лимита. Используется значение по умолчанию: 5 минут${RESET}"
            WAIT_SECONDS=300
        fi
        
        # Добавляем небольшую задержку для надежности
        WAIT_SECONDS=$((WAIT_SECONDS + 10))
        
        # Форматируем время ожидания
        WAIT_FORMATTED=$(format_time $WAIT_SECONDS)
        RESET_TIME=$(date -d "+${WAIT_SECONDS} seconds" '+%H:%M:%S' 2>/dev/null || date -v+${WAIT_SECONDS}S '+%H:%M:%S' 2>/dev/null || echo "через ~$((WAIT_SECONDS / 60)) мин")
        
        echo -e "${YELLOW}⏳ Ожидание сброса лимита...${RESET}"
        echo -e "${YELLOW}   Время ожидания: ${BOLD}${WAIT_FORMATTED}${RESET}"
        echo -e "${YELLOW}   Ожидаемое время сброса: ${BOLD}${RESET_TIME}${RESET}"
        echo ""
        
        # Обратный отсчет с МЕГА-анимацией! 🎨✨
        INITIAL_WAIT=$WAIT_SECONDS
        FRAME=0
        
        # Радужные цвета ANSI (256 цветов)
        RAINBOW_COLORS=(
            "\033[38;5;196m"  # Красный
            "\033[38;5;202m"  # Оранжевый
            "\033[38;5;226m"  # Желтый
            "\033[38;5;46m"   # Зеленый
            "\033[38;5;51m"   # Голубой
            "\033[38;5;21m"   # Синий
            "\033[38;5;129m"  # Фиолетовый
            "\033[38;5;201m"  # Розовый
        )
        
        # Разные наборы спиннеров
        SPINNER_SETS=(
            "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            "◐◓◑◒"
            "◴◷◶◵"
            "⣾⣽⣻⢿⡿⣟⣯⣷"
            "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁"
            "▉▊▋▌▍▎▏▎▍▌▋▊▉"
            "◆◇◆◇"
            "✦✧✦✧"
        )
        SPINNER_SET_INDEX=0
        SPINNER_CHAR_INDEX=0
        
        # Частицы для эффекта
        PARTICLES=("·" "•" "○" "●" "◉" "◯" "◐" "◑" "◒" "◓")
        
        # Эмодзи для дополнительной анимации
        EMOJI_SEQUENCE=("⏳" "⏰" "⏱️" "🕐" "🕑" "🕒" "🕓" "🕔" "🕕" "🕖" "🕗" "🕘" "✨" "🌟" "💫" "⭐")
        EMOJI_INDEX=0
        
        # Символы для прогресс-бара
        PROGRESS_CHARS=("░" "▒" "▓" "█" "▉" "▊" "▋" "▌" "▍" "▎" "▏")
        
        while [ $WAIT_SECONDS -gt 0 ]; do
            # Форматируем оставшееся время
            TIME_REMAINING=$(format_time $WAIT_SECONDS)
            
            # Вычисляем прогресс-бар (30 символов)
            TOTAL_BARS=30
            ELAPSED=$((INITIAL_WAIT - WAIT_SECONDS))
            FILLED=$((ELAPSED * TOTAL_BARS / INITIAL_WAIT))
            PROGRESS_PERCENT=$((ELAPSED * 100 / INITIAL_WAIT))
            
            # Создаем РАДУЖНЫЙ прогресс-бар! 🌈
            PROGRESS_BAR=""
            for ((i=0; i<FILLED; i++)); do
                # Радужный эффект - цвет меняется по позиции
                COLOR_INDEX=$(((i + FRAME) % ${#RAINBOW_COLORS[@]}))
                CHAR_INDEX=$(((i + FRAME) % ${#PROGRESS_CHARS[@]}))
                PROGRESS_BAR="${PROGRESS_BAR}${RAINBOW_COLORS[$COLOR_INDEX]}${PROGRESS_CHARS[-1]}${RESET}"
            done
            
            # Анимированная граница с эффектом пульсации
            if [ $FILLED -lt $TOTAL_BARS ]; then
                WAVE_CHAR_INDEX=$((FRAME % ${#PROGRESS_CHARS[@]}))
                PULSE_COLOR=$((FRAME % ${#RAINBOW_COLORS[@]}))
                PROGRESS_BAR="${PROGRESS_BAR}${RAINBOW_COLORS[$PULSE_COLOR]}${PROGRESS_CHARS[$WAVE_CHAR_INDEX]}${RESET}"
            fi
            
            # Заполняем пустую часть с эффектом "тумана"
            REMAINING=$((TOTAL_BARS - FILLED - 1))
            for ((i=0; i<REMAINING; i++)); do
                FOG_CHAR=$(( (FRAME + i) % 3 ))
                case $FOG_CHAR in
                    0) FOG_SYMBOL="░" ;;
                    1) FOG_SYMBOL="▒" ;;
                    *) FOG_SYMBOL="▓" ;;
                esac
                PROGRESS_BAR="${PROGRESS_BAR}${GRAY}${FOG_SYMBOL}${RESET}"
            done
            
            # Получаем текущий набор спиннеров
            CURRENT_SPINNER_SET="${SPINNER_SETS[$SPINNER_SET_INDEX]}"
            SPINNER_LENGTH=${#CURRENT_SPINNER_SET}
            SPINNER="${CURRENT_SPINNER_SET:$SPINNER_CHAR_INDEX:1}"
            
            # Радужный спиннер
            SPINNER_COLOR_INDEX=$((FRAME % ${#RAINBOW_COLORS[@]}))
            COLORED_SPINNER="${RAINBOW_COLORS[$SPINNER_COLOR_INDEX]}${SPINNER}${RESET}"
            
            # Обновляем индексы спиннера
            SPINNER_CHAR_INDEX=$(((SPINNER_CHAR_INDEX + 1) % SPINNER_LENGTH))
            if [ $SPINNER_CHAR_INDEX -eq 0 ]; then
                SPINNER_SET_INDEX=$(((SPINNER_SET_INDEX + 1) % ${#SPINNER_SETS[@]}))
            fi
            
            # Обновляем эмодзи
            if [ $((FRAME % 2)) -eq 0 ]; then
                EMOJI="${EMOJI_SEQUENCE[$EMOJI_INDEX]}"
                EMOJI_INDEX=$(((EMOJI_INDEX + 1) % ${#EMOJI_SEQUENCE[@]}))
            fi
            
            # Радужный текст времени с пульсацией
            TIME_COLOR_INDEX=$(((FRAME / 2) % ${#RAINBOW_COLORS[@]}))
            PULSE=$((FRAME % 8))
            if [ $PULSE -lt 4 ]; then
                TIME_COLOR="${BOLD}${RAINBOW_COLORS[$TIME_COLOR_INDEX]}"
            else
                TIME_COLOR="${RAINBOW_COLORS[$TIME_COLOR_INDEX]}"
            fi
            
            # Процент с радужным эффектом
            PERCENT_COLOR_INDEX=$(((FRAME + 5) % ${#RAINBOW_COLORS[@]}))
            
            # Генерируем частицы для эффекта (ограничиваем до 10 частиц для правильного выравнивания)
            PARTICLES_LINE=""
            PARTICLE_COUNT=0
            for ((i=0; i<20 && PARTICLE_COUNT<10; i++)); do
                if [ $(( (FRAME + i) % 3 )) -eq 0 ]; then
                    PARTICLE_COLOR_INDEX=$(( (i + FRAME) % ${#RAINBOW_COLORS[@]} ))
                    PARTICLE_INDEX=$(( (FRAME + i) % ${#PARTICLES[@]} ))
                    PARTICLES_LINE="${PARTICLES_LINE}${RAINBOW_COLORS[$PARTICLE_COLOR_INDEX]}${PARTICLES[$PARTICLE_INDEX]}${RESET} "
                    PARTICLE_COUNT=$((PARTICLE_COUNT + 1))
                else
                    PARTICLES_LINE="${PARTICLES_LINE}  "
                fi
            done
            
            # Радужная рамка
            FRAME_COLOR_INDEX=$((FRAME % ${#RAINBOW_COLORS[@]}))
            FRAME_COLOR="${RAINBOW_COLORS[$FRAME_COLOR_INDEX]}"
            
            # ASCII-арт элементы
            CORNER_TL="${FRAME_COLOR}╔${RESET}"
            CORNER_TR="${FRAME_COLOR}╗${RESET}"
            CORNER_BL="${FRAME_COLOR}╚${RESET}"
            CORNER_BR="${FRAME_COLOR}╝${RESET}"
            H_LINE="${FRAME_COLOR}═${RESET}"
            V_LINE="${FRAME_COLOR}║${RESET}"
            
            # Анимированный заголовок
            HEADER_COLOR_INDEX=$(((FRAME / 3) % ${#RAINBOW_COLORS[@]}))
            HEADER_COLOR="${RAINBOW_COLORS[$HEADER_COLOR_INDEX]}"
            
            # Выводим МЕГА-многострочную анимацию! 🎆
            # Перемещаемся на 9 строк вверх (если это не первая итерация)
            # Всего 9 строк: верхняя рамка, заголовок, пустая, время, пустая, прогресс, пустая, частицы, нижняя рамка
            if [ $FRAME -gt 0 ]; then
                printf "\033[9A"
            fi
            
            # Ширина рамки: 60 символов (58 горизонтальных + 2 угла)
            FRAME_WIDTH=60
            
            # Верхняя рамка
            printf "\r\033[K${CORNER_TL}"
            for i in {1..58}; do printf "${H_LINE}"; done
            printf "${CORNER_TR}\n"
            
            # Строка с заголовком
            HEADER_TEXT="${EMOJI} ${HEADER_COLOR}Ожидание сброса лимита${RESET}"
            printf "\r\033[K  ${HEADER_TEXT}\n"
            
            # Пустая строка
            printf "\r\033[K\n"
            
            # Строка с временем
            printf "\r\033[K  "
            printf "${COLORED_SPINNER} ${TIME_COLOR}⏱️  Осталось: ${TIME_COLOR}${TIME_REMAINING}${RESET}\n"
            
            # Пустая строка
            printf "\r\033[K\n"
            
            # Строка с прогресс-баром
            printf "\r\033[K  "
            printf "${PROGRESS_BAR} ${RAINBOW_COLORS[$PERCENT_COLOR_INDEX]}[%3d%%]${RESET}\n" $PROGRESS_PERCENT
            
            # Пустая строка
            printf "\r\033[K\n"
            
            # Строка с частицами
            PARTICLES_FIXED=""
            PARTICLE_COUNT=0
            for ((i=0; i<${#PARTICLES[@]} && PARTICLE_COUNT<9; i++)); do
                if [ $(( (FRAME + i) % 3 )) -eq 0 ]; then
                    PARTICLE_COLOR_INDEX=$(( (i + FRAME) % ${#RAINBOW_COLORS[@]} ))
                    PARTICLE_INDEX=$(( (FRAME + i) % ${#PARTICLES[@]} ))
                    PARTICLES_FIXED="${PARTICLES_FIXED}${RAINBOW_COLORS[$PARTICLE_COLOR_INDEX]}${PARTICLES[$PARTICLE_INDEX]}${RESET} "
                    PARTICLE_COUNT=$((PARTICLE_COUNT + 1))
                else
                    PARTICLES_FIXED="${PARTICLES_FIXED}  "
                fi
            done
            printf "\r\033[K  ${PARTICLES_FIXED}\n"
            
            # Нижняя рамка
            printf "\r\033[K${CORNER_BL}"
            for i in {1..58}; do printf "${H_LINE}"; done
            printf "${CORNER_BR}\n"
            
            sleep 0.15
            FRAME=$((FRAME + 1))
            
            # Обновляем секунды каждые ~7 кадров (1 секунда при sleep 0.15)
            if [ $((FRAME % 7)) -eq 0 ]; then
                WAIT_SECONDS=$((WAIT_SECONDS - 1))
            fi
        done
        
        # Финальный эффект - "взрыв" радуги! 🎆
        # Очищаем текущую анимацию перед финальным эффектом
        printf "\033[9A"  # Перемещаемся на 9 строк вверх
        for i in {1..9}; do
            printf "\r\033[K\n"  # Очищаем каждую строку
        done
        printf "\033[9A"  # Возвращаемся наверх
        
        for i in {1..3}; do
            for color in "${RAINBOW_COLORS[@]}"; do
                # Верхняя рамка
                printf "\r\033[K${color}╔"
                for j in {1..58}; do printf "═"; done
                printf "╗${RESET}\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Сообщение
                MSG="${color}${BOLD}✨ ЛИМИТ СБРОШЕН! ✨${RESET}"
                printf "\r\033[K  ${MSG}\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Пустая строка
                printf "\r\033[K\n"
                
                # Нижняя рамка
                printf "\r\033[K${color}╚"
                for j in {1..58}; do printf "═"; done
                printf "╝${RESET}\n"
                
                # Возвращаемся наверх для следующей итерации
                printf "\033[9A"
                
                sleep 0.05
            done
        done
        
        # Очищаем анимацию (9 строк)
        # Перемещаемся наверх и очищаем каждую строку полностью
        printf "\033[9A"  # Перемещаемся на 9 строк вверх (к началу анимации)
        for i in {1..9}; do
            printf "\r\033[K"  # Очищаем текущую строку полностью
            if [ $i -lt 9 ]; then
                printf "\033[1B"  # Переходим на следующую строку вниз
            fi
        done
        # Теперь мы на последней строке анимации, очищаем её и остаемся там
        
        echo ""
        echo ""
        echo -e "${GREEN}✅ Лимит сброшен, продолжаем работу...${RESET}"
        echo ""
    fi
    
    # Пауза перед следующим запуском
    echo -e "${GRAY}⏳ Пауза ${YELLOW}${PAUSE_SECONDS} секунд${GRAY} перед следующей итерацией...${RESET}"
    echo ""
    sleep $PAUSE_SECONDS
    
    ITERATION=$((ITERATION + 1))
done
