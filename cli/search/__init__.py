from cli.search.commands import edit, list_tickets, show
from cli.search.search import search

search.add_command(list_tickets)
search.add_command(show)
search.add_command(edit)
