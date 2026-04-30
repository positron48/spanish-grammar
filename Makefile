# Makefile для управления проектом spanish-grammar (конвейер как у english-grammar)

.PHONY: help sync-plan final final-all final-force validate-all validate-uniqueness training-pack training-pack-append training-pack-fill training-pack-admin clean admin run test dev update-admin-index update-test-index

# Находим все главы (с префиксами или без)
# Сортируем по номеру префикса (001, 002, ...), затем извлекаем chapter_id
CHAPTERS := $(shell find chapters -mindepth 1 -maxdepth 1 -type d -not -name '.*' | sed 's|chapters/||' | sort -V | sed 's|^[0-9][0-9][0-9]\.||' | awk '!seen[$$0]++')

help:
	@echo "Доступные команды:"
	@echo "  make sync-plan          - Синхронизировать generation-status и chapter templates из 01-sections.md"
	@echo "  make final              - Пересобрать final.json для всех глав"
	@echo "  make final-all          - Принудительно пересобрать все final.json для всех глав"
	@echo "  make final-force        - Алиас для make final-all (принудительная пересборка всех глав)"
	@echo "  make validate-all        - Валидировать все главы"
	@echo "  make validate-uniqueness - Проверить уникальность вопросов по всему курсу"
	@echo "  make training-pack       - Сгенерировать training_pack через локальную LLM (с нуля)"
	@echo "  make training-pack-append - Догенерить новые вопросы к существующему training_pack"
	@echo "  make training-pack-fill   - Пройти все theory блоки и добить валидные вопросы до целевого порога"
	@echo "  make training-pack-admin  - Легкая визуальная админка для training_pack (без сборки)"
	@echo "  make admin               - Запустить админ-панель для просмотра глав"
	@echo "  make run                 - Запустить тестовую систему для изучения курса"
	@echo "  make test                - Алиас для make run (тестовая система)"
	@echo "  make dev                 - Запустить оба сервера (admin + test)"
	@echo "  make clean               - Удалить временные файлы"
	@echo ""
	@echo "Найдено глав: $(words $(CHAPTERS))"
	@echo "$(foreach ch,$(CHAPTERS),  - $(ch)$(newline))"

# Синхронизация плана курса и шаблонов входных файлов
sync-plan:
	@python3 scripts/sync-course-plan.py

# Пересобрать final.json для всех глав
final:
	@echo "Пересборка final.json для всех глав..."
	@UPDATED=0; FAILED=0; \
	for chapter in $(CHAPTERS); do \
		echo "  🔨 Пересборка: $$chapter"; \
		if bash scripts/assemble-chapter.sh $$chapter > /dev/null 2>&1; then \
			UPDATED=$$((UPDATED + 1)); \
		else \
			echo "    ✗ Ошибка при сборке $$chapter"; \
			FAILED=$$((FAILED + 1)); \
		fi; \
	done; \
	echo ""; \
	echo "✓ Пересборка завершена: обновлено $$UPDATED глав"; \
	if [ $$FAILED -gt 0 ]; then \
		echo "  ⚠️  Ошибок: $$FAILED глав"; \
	fi

# Принудительно пересобрать все final.json
final-all:
	@echo "Принудительная пересборка final.json для всех глав..."
	@UPDATED=0; FAILED=0; \
	for chapter in $(CHAPTERS); do \
		echo "  🔨 Пересборка: $$chapter"; \
		if bash scripts/assemble-chapter.sh $$chapter > /dev/null 2>&1; then \
			UPDATED=$$((UPDATED + 1)); \
		else \
			echo "    ✗ Ошибка при сборке $$chapter"; \
			FAILED=$$((FAILED + 1)); \
		fi; \
	done; \
	echo ""; \
	echo "✓ Пересборка завершена: обновлено $$UPDATED глав"; \
	if [ $$FAILED -gt 0 ]; then \
		echo "  ⚠️  Ошибок: $$FAILED глав"; \
	fi

# Алиас для принудительной пересборки всех глав
final-force: final-all

# Валидировать все главы
validate-all:
	@for chapter in $(CHAPTERS); do \
		bash scripts/validate-chapter.sh $$chapter; \
	done
	@echo ""
	@echo "Проверка уникальности вопросов по всему курсу..."
	@bash scripts/validate-course-uniqueness.sh || true

# Проверить уникальность вопросов по всему курсу
validate-uniqueness:
	@bash scripts/validate-course-uniqueness.sh

training-pack:
	@echo "Сборка training_pack (llm-only, replace mode)..."
	@set -a; [ -f .env.local ] && . ./.env.local; set +a; \
	python3 scripts/generate-training-pack.py --course-root .
	@echo "✓ training_pack готов"

training-pack-append:
	@echo "Догенерация training_pack (llm-only, append mode)..."
	@set -a; [ -f .env.local ] && . ./.env.local; set +a; \
	python3 scripts/generate-training-pack.py --course-root . --append
	@echo "✓ training_pack готов"

training-pack-fill:
	@echo "Fill training_pack for all theory blocks (llama.cpp default)..."
	@caffeinate -dimsu python3 scripts/fill-training-pack.py \
		--course-root . \
		--batch-size 10 \
		--target-valid 1
	@echo "✓ fill complete"

training-pack-admin:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🧩 TRAINING PACK ADMIN (lightweight, no prebuild)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Откройте: http://127.0.0.1:8010/"
	@echo "Остановка: Ctrl+C"
	@python3 training-pack-admin/server.py --course-root . --port 8010

# Очистка временных файлов
clean:
	@echo "Очистка временных файлов..."
	@find . -type f -name "*.tmp" -delete
	@find . -type f -name "*~" -delete
	@echo "✓ Очистка завершена"

# Проверка и обновление индекса админ-панели
update-admin-index:
	@echo "Обновление индекса админ-панели..."; \
	node admin/generate-index.js || (echo "❌ Ошибка: Node.js не найден. Установите Node.js для работы админ-панели." && exit 1); \
	echo "✓ Индекс админ-панели обновлен"

# Проверка и обновление индекса тестовой системы
update-test-index:
	@echo "Обновление индекса тестовой системы..."; \
	node test/scripts/generate-chapters-index.js && echo "✓ Индекс тестовой системы обновлен" || (echo "⚠️  Предупреждение: Node.js не найден. Индекс не будет обновлен." && echo "   Для автоматического обновления индекса установите Node.js.")

# Запуск админ-панели
admin:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📚 АДМИН-ПАНЕЛЬ: Система просмотра и валидации курсов грамматики"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Что это:"
	@echo "  Визуальная система для просмотра всех глав курса, проверки содержания,"
	@echo "  компоновки, списка всех тестов и результатов валидации."
	@echo ""
	@echo "Функции:"
	@echo "  • Просмотр всех глав с фильтрацией и поиском"
	@echo "  • Детальный просмотр каждой главы (теория, вопросы, квизы, валидация)"
	@echo "  • Статистика по главам и вопросам"
	@echo "  • Проверка результатов валидации"
	@echo ""
	@$(MAKE) -s update-admin-index
	@if [ ! -f admin/data/chapters-index.json ]; then \
		echo "❌ Ошибка: Индекс не был создан. Проверьте права доступа."; \
		exit 1; \
	fi
	@echo ""
	@echo "Запуск локального веб-сервера..."
	@if command -v php >/dev/null 2>&1; then \
		echo "✓ PHP найден, запускаем PHP сервер (необходим для работы API)..."; \
	else \
		echo "⚠️  ВНИМАНИЕ: PHP не найден!"; \
		echo "   Для работы функций удаления вопросов необходим PHP сервер."; \
		echo "   Установите PHP: sudo apt install php"; \
		echo ""; \
		echo "   Запускаем Python сервер (ограниченная функциональность - удаление вопросов не работает)..."; \
	fi
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Сервер запущен!"
	@echo ""
	@echo "🌐 Откройте в браузере:"
	@echo "   http://localhost:8000/admin/"
	@echo ""
	@echo "📖 Для остановки нажмите Ctrl+C"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@if command -v php >/dev/null 2>&1; then \
		php -S localhost:8000 -t . 2>/dev/null || \
		(echo "❌ Ошибка запуска PHP сервера" && exit 1); \
	else \
		python3 -m http.server 8000 2>/dev/null || \
		(echo "❌ Ошибка: Не найден Python3 или PHP для запуска сервера." && \
		 echo "   Установите PHP: sudo apt install php" && \
		 echo "   Или Python3: sudo apt install python3" && exit 1); \
	fi

# Запуск тестовой системы для изучения
run:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📚 ТЕСТОВАЯ СИСТЕМА: Интерактивный курс изучения английской грамматики"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@$(MAKE) -s update-test-index
	@echo ""
	@echo "Что это:"
	@echo "  Готовая система для изучения курса грамматики с категориями, теорией,"
	@echo "  inline-квизами в теле глав и финальным рандомизированным тестированием."
	@echo ""
	@echo "Функции:"
	@echo "  • Навигация по разделам и главам курса"
	@echo "  • Изучение теории с примерами и ключевыми моментами"
	@echo "  • Inline-квизы для закрепления материала после каждого теоретического блока"
	@echo "  • Финальные тесты с рандомизацией вопросов по стратегии отбора"
	@echo "  • Детальные результаты тестов с объяснениями"
	@echo ""
	@echo "Запуск локального веб-сервера..."
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Сервер запущен!"
	@echo ""
	@echo "🌐 Откройте в браузере:"
	@echo "   http://localhost:8001/test/"
	@echo ""
	@echo "📖 Структура курса:"
	@echo "   - Главная страница с разделами и главами: http://localhost:8001/test/"
	@echo "   - Страница главы с теорией и квизами: http://localhost:8001/test/chapter.html"
	@echo "   - Страница финального теста: http://localhost:8001/test/test.html"
	@echo ""
	@echo "💡 Для остановки сервера нажмите Ctrl+C"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@python3 -m http.server 8001 2>/dev/null || \
	 (php -S localhost:8001 2>/dev/null) || \
	 (echo "❌ Ошибка: Не найден Python3 или PHP для запуска сервера." && \
	  echo "   Установите Python3: sudo apt install python3" && \
	  echo "   Или PHP: sudo apt install php" && exit 1)

# Алиас для команды run
test: run

# Запуск обоих серверов одновременно с автообновлением
dev:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🚀 ЗАПУСК РАЗРАБОТКИ: Админ-панель + Тестовая система"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Обновление индексов..."
	@$(MAKE) -s update-admin-index >/dev/null 2>&1 || true
	@$(MAKE) -s update-test-index >/dev/null 2>&1 || true
	@echo "✓ Индексы обновлены"
	@echo ""
	@echo "Запуск серверов..."
	@echo ""
	@bash -c '\
		cleanup() { \
			echo ""; \
			echo "🛑 Остановка серверов..."; \
			trap "" INT TERM; \
			if [ -n "$$PIDS" ]; then \
				for pid in $$PIDS; do \
					kill $$pid 2>/dev/null || true; \
				done; \
				sleep 0.1; \
				for pid in $$PIDS; do \
					kill -9 $$pid 2>/dev/null || true; \
				done; \
			fi; \
			exit 0; \
		}; \
		trap cleanup INT TERM; \
		PIDS=""; \
		echo "📚 Запуск админ-панели (http://localhost:8000/admin/)..."; \
		if command -v php >/dev/null 2>&1; then \
			php -S localhost:8000 -t . >/dev/null 2>&1 & \
			PIDS="$$PIDS $$!"; \
		else \
			python3 -m http.server 8000 >/dev/null 2>&1 & \
			PIDS="$$PIDS $$!"; \
		fi; \
		echo "📚 Запуск тестовой системы (http://localhost:8001/test/)..."; \
		if command -v python3 >/dev/null 2>&1; then \
			python3 -m http.server 8001 >/dev/null 2>&1 & \
			PIDS="$$PIDS $$!"; \
		elif command -v php >/dev/null 2>&1; then \
			php -S localhost:8001 >/dev/null 2>&1 & \
			PIDS="$$PIDS $$!"; \
		fi; \
		echo ""; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "✅ Серверы запущены!"; \
		echo ""; \
		echo "🌐 Админ-панель:  http://localhost:8000/admin/"; \
		echo "🌐 Тестовая система: http://localhost:8001/test/"; \
		echo ""; \
		echo "📖 Для остановки нажмите Ctrl+C"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo ""; \
		for pid in $$PIDS; do \
			wait $$pid 2>/dev/null || true; \
		done'
