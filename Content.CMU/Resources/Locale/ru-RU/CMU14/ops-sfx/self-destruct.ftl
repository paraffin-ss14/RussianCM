# Тексты оповещений для последовательности самоуничтожения (self_destruct.yml).
# Реплики MU/TH/UR из фильма; разметка соответствует белому списку тегов панели оповещений.
-cmu-ops-sfx-muthur-header = [color=#4d6b58]MU/TH/UR 6000 :: АВАРИЙНЫЙ ИНТЕРФЕЙС САМОУНИЧТОЖЕНИЯ[/color]

cmu-ops-sfx-activated =
    {-cmu-ops-sfx-muthur-header}
    {"["}bold][color=#ff3838]ОПАСНОСТЬ![/color][/bold] Система аварийного самоуничтожения [bold][color=#ff3838]активирована[/color][/bold]...

cmu-ops-sfx-destruct-with-override =
    {-cmu-ops-sfx-muthur-header}
    Корабль взорвётся через... [bold][color=#ffb000]{$detonation}[/color][/bold]... Возможность отменить автоматическую детонацию истекает через... [bold][color=#ffb000]{$override}[/color][/bold].

cmu-ops-sfx-override-expires =
    {-cmu-ops-sfx-muthur-header}
    Возможность отменить автоматическую детонацию истекает через... [bold][color=#ffb000]{$time}[/color][/bold]{$punct}

cmu-ops-sfx-override-expired =
    {-cmu-ops-sfx-muthur-header}
    Возможность отменить процедуру детонации [bold][color=#ff3838]утрачена[/color][/bold].

cmu-ops-sfx-destruct-countdown =
    {-cmu-ops-sfx-muthur-header}
    Корабль автоматически самоуничтожится через... [bold][color=#ffb000]{$time}[/color][/bold]...

cmu-ops-sfx-abandon-1 =
    {-cmu-ops-sfx-muthur-header}
    У вас осталось [bold][color=#ffb000]1 минута[/color][/bold], чтобы [bold][color=#ff3838]покинуть корабль[/color][/bold].

cmu-ops-sfx-t-30 =
    {-cmu-ops-sfx-muthur-header}
    {"["}bold][color=#ff3838]До детонации 30 секунд.[/color][/bold]

cmu-ops-sfx-structural-failures =
    {-cmu-ops-sfx-muthur-header}
    {"["}bold][color=#ff3838]ВНИМАНИЕ.[/color][/bold] По всему кораблю обнаружены множественные катастрофические разрушения конструкции.

cmu-ops-sfx-total-collapse =
    {-cmu-ops-sfx-muthur-header}
    {"["}bold][color=#ff3838]ИДЁТ ПОЛНОЕ РАЗРУШЕНИЕ КОНСТРУКЦИИ.[/color][/bold]
