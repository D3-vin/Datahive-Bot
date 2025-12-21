"""
Simple menu for Datahive
"""

import os
from typing import Optional

from colorama import Fore, Style, init
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

init(autoreset=True)


class DatahiveMenu:
    """Simple menu for Datahive"""
    
    def __init__(self):
        self.console = Console()
    
    def clear_screen(self) -> None:
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_welcome(self) -> None:
        """Show welcome screen"""
        self.console.clear()
        
        combined_text = Text()
        combined_text.append("\n📢 Channel: ", style="bold white")
        combined_text.append("https://t.me/D3_vin", style="cyan")
        combined_text.append("\n💬 Chat: ", style="bold white")
        combined_text.append("https://t.me/D3vin_chat", style="cyan")
        combined_text.append("\n📁 GitHub: ", style="bold white")
        combined_text.append("https://github.com/D3-vin", style="cyan")
        combined_text.append("\n📁 Version: ", style="bold white")
        combined_text.append("1.0", style="green")
        combined_text.append("\n")

        info_panel = Panel(
            Align.left(combined_text),
            title="[bold blue]Datahive Bot[/bold blue]",
            subtitle="[bold magenta]Dev by D3vin[/bold magenta]",
            box=box.ROUNDED,
            border_style="bright_blue",
            padding=(0, 1),
            width=50
        )

        self.console.print(info_panel)
        self.console.print()
    
    def show_menu(self) -> int:
        """Show main menu and get user choice"""
        table = Table(
            show_header=False,
            box=None,
            border_style="bright_blue",
            expand=False,
            width=50,
            padding=(0, 1)
        )
        
        table.add_column("Menu Options", style="white", justify="left")
        
        options = [
            "1 Registration",
            "2 Farming",
            "3 Exit"
        ]
        
        for option in options:
            table.add_row(f"[bold bright_cyan]{option}[/bold bright_cyan]")
        
        menu_panel = Panel(
            table,
            title="[bold blue]📋 Menu[/bold blue]",
            border_style="bright_blue",
            padding=(0, 1),
            width=50
        )
        
        self.console.print(menu_panel)
        
        # Get user input
        while True:
            try:
                choice = input(f"\n{Fore.CYAN}Enter choice [1-3]: {Style.RESET_ALL}")
                choice_int = int(choice)
                if choice_int in [1, 2, 3]:
                    return choice_int
                else:
                    print(f"{Fore.RED}Invalid choice. Please enter 1, 2, or 3.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
            except KeyboardInterrupt:
                return 4
    
    def show_operation_info(self, operation: str, count: int) -> None:
        """Show operation information"""
        self.clear_screen()
        self.show_welcome()
        
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Info", style="bold white", width=15)
        info_table.add_column("Value", style="cyan", width=20)
        
        info_table.add_row("Operation:", operation)
        info_table.add_row("Accounts:", str(count))
        
        info_panel = Panel(
            info_table,
            title=f"[bold green]Starting {operation}[/bold green]",
            border_style="green"
        )
        
        self.console.print(info_panel)
        print()


# Global menu instance
_menu_instance: Optional[DatahiveMenu] = None


def get_menu() -> DatahiveMenu:
    """Get global menu instance"""
    global _menu_instance
    if _menu_instance is None:
        _menu_instance = DatahiveMenu()
    return _menu_instance