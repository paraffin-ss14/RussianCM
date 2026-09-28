# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 wray-git
# SPDX-License-Identifier: AGPL-3.0-only
# Строка осмотра, отображаемая на любой сущности, построенной игроком.
construction-player-built-examine = Построено [color=cyan]{ $name }[/color].

# Действия с партнёром по строительству (ПКМ по другому игроку).
build-partner-add-verb = Добавить как партнёра по строительству
build-partner-remove-verb = Удалить партнёра по строительству
build-partner-added = { $name } теперь может включать ваши постройки в свои сохранения.
build-partner-removed = { $name } больше не может включать ваши постройки в свои сохранения.

# Сохранение построек.
saved-build-success = Постройка «{ $name }» сохранена ({ $count } сущностей, { $tiles } тайлов).
saved-build-error-no-name = Сначала укажите название постройки.
saved-build-error-empty = В выбранной области нет ничего, построенного вами или вашим партнёром.
saved-build-error-serialize = Не удалось сериализовать эту постройку.
saved-build-error-write = Не удалось записать файл постройки.

# Панель выбора области сохранения постройки (клиент).
saved-build-window-title = Сохранить постройку
saved-build-window-range = Радиус
saved-build-window-size = Выбранная область: { $size }x{ $size } тайлов
saved-build-window-append = Добавить область
saved-build-window-clear = Очистить
saved-build-window-selected = Выделено: { $count } сущностей, { $tiles } тайлов
saved-build-window-multiz-help = Сохранение нескольких Z-уровней является экспериментальным:
    - Постройки с несколькими Z-уровнями работают только при использовании «Разместить в исходном месте».
    - Размещайте исходную постройку отдельно на каждом Z-уровне: постройте один уровень, перейдите на следующий, затем снова используйте «Разместить в исходном месте».
    - Для наилучшей стабильности создавайте отдельное сохранение для каждого Z-уровня.
saved-build-window-name = Название постройки…
saved-build-window-save = Сохранить постройку
saved-build-window-open-folder = Открыть папку сохранённых построек
saved-build-window-include-tiles = Сохранять тайлы
saved-build-window-include-multiz = Захватывать другие Z-уровни (выше/ниже)

# Список сохранённых построек в меню строительства.
gmod-construction-menu-saved-builds = Сохранённые постройки
saved-build-card = { $name }  ({ $author } · { $count })
saved-build-detail-desc = Автор: { $author }
    { $count } сущностей · { $source }
saved-build-none = Сохранённых построек пока нет. Используйте инструмент сохранения построек, чтобы создать одну.
saved-build-place-button = Разместить постройку
saved-build-placed = Постройка размещена ({ $count } элементов).
saved-build-error-load = Не удалось загрузить эту сохранённую постройку.
saved-build-error-nogrid = Постройку можно размещать только на гриде.
saved-build-error-noorigin = Исходное местоположение этой постройки больше не существует.
saved-build-error-notadmin = Только администраторы могут размещать постройки мгновенно. Используйте призраки строительства и возведите её вручную.
saved-build-place-original-button = Разместить в исходном месте
saved-build-ghosts-placed = Размещено призраков строительства: { $count } — постройте их, используя материалы.

# Управление сохранёнными постройками (удаление + открытие папки).
gmod-construction-menu-delete-build = Удалить постройку
gmod-construction-menu-open-build-folder = Открыть папку построек
saved-build-deleted = Сохранённая постройка удалена.
saved-build-error-delete = Не удалось удалить сохранённую постройку.
saved-build-error-delete-notyours = Вы можете удалять только сохранённые вами постройки. (Администраторы могут удалять любые.)

# Выпадающий список режима строительства в верхней части меню строительства.
gmod-construction-menu-mode-admin = Строительство: Администратор (мгновенно)
gmod-construction-menu-mode-player = Строительство: Игрок (призраки)
gmod-construction-menu-mode-mapper = Строительство: Маппер (любая сущность)

# Окно партнёров по строительству (кнопка «Партнёры»).
build-partner-window-title = Партнёры по строительству
build-partner-window-desc = Добавьте игрока, чтобы он мог включать ВАШИ построенные объекты в свои сохранённые постройки.
build-partner-window-empty = Других игроков в сети нет.
build-partner-window-add = Добавить
build-partner-window-remove = Удалить
build-partner-window-clear-all = Удалить всех партнёров
build-partner-granted-to-you = { $name } добавил вас как партнёра по строительству — теперь вы можете сохранять его постройки.
build-partner-revoked-from-you = { $name } удалил вас из партнёров по строительству.

# Дополнительная настройка окна сохранения (режим маппера) + переименование/удаление в панели сведений.
saved-build-window-include-loose = Включать отдельные предметы
gmod-construction-menu-rename-build = Переименовать
gmod-construction-menu-delete-build-confirm = Подтвердить удаление?

# Подсказка по управлению размещением (левый верхний угол).
saved-build-controls-mode-admin = Режим: Администратор (мгновенно, бесплатно)
saved-build-controls-mode-player = Режим: Строительство (призраки + материалы)
saved-build-controls-gridalign = Alt (переключить): Выравнивание по сетке ({ $state })
saved-build-controls-rotate = { $key }: Повернуть
saved-build-controls-place = ЛКМ: Разместить
saved-build-controls-cancel = ПКМ: Отмена

# Размещение на нескольких Z-уровнях
saved-build-z-skipped = Не удалось разместить сущностей: {$count} — их Z-уровень невозможно создать здесь.
