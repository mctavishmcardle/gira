from cli.search.commands import add, edit, list_tickets, set_properties, show, stage
from cli.search.search import search_tickets

search_tickets.add_command(list_tickets)
search_tickets.add_command(show)
search_tickets.add_command(edit)
search_tickets.add_command(set_properties)
search_tickets.add_command(add)
search_tickets.add_command(stage)
