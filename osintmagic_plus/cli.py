import asyncio
import click
from rich.console import Console
from rich.traceback import install as rich_install

from .core.config import AppConfig
from .core.logging_setup import setup_logging
from .core.pipeline import run_pipeline

console = Console()
rich_install(show_locals=False)

@click.command()
@click.option("--name", type=str, help="ФИО персоны")
@click.option("--phone", type=str, help="Телефон (в международном формате)")
@click.option("--email", type=str, help="Email")
@click.option("--username", type=str, help="Юзернейм (ник)")
@click.option("--birth-year", type=int, help="Год рождения")
@click.option("--city", type=str, help="Город")
@click.option("--country", type=str, help="Страна")
@click.option("--providers", type=str, default="brave", help="Список провайдеров через запятую: brave,bing,google")
@click.option("--output-format", type=click.Choice(["html","json","markdown"]), default="html")
@click.option("--log-level", type=click.Choice(["debug","info","warning","error"]), default="info")
@click.option("--timeout", type=int, default=10, help="Таймаут запроса (сек)")
@click.option("--max-concurrent", type=int, default=50, help="Макс. одновременных запросов")
@click.option("--no-darkweb", is_flag=True, default=False, help="Отключить .onion источники")
@click.option("--cache-ttl", type=int, default=86400, help="Время жизни кэша (сек)")
@click.option("--fresh", is_flag=True, default=False, help="Игнорировать кэш")
@click.option("--tor", is_flag=True, default=False, help="Включить Tor для сетевых запросов (этика, риски!)")
@click.option("--depth", type=click.IntRange(1,4), default=1, help="Глубина поиска (1..4)")

def main(**kwargs):
    """Запуск конвейера OSINT-поиска и генерации отчёта."""
    cfg = AppConfig.from_cli_kwargs(kwargs)
    setup_logging(cfg.log_level)
    console.log(f"[bold]osintmagic-plus[/bold] стартует с глубиной поиска {cfg.depth}")

    try:
        asyncio.run(run_pipeline(cfg))
    except KeyboardInterrupt:
        console.log("[yellow]Остановлено пользователем[/yellow]")
    except Exception as e:
        console.print_exception()

if __name__ == "__main__":
    main()
