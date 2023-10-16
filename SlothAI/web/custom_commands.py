from flask import Blueprint, render_template
from flask import current_app as app

custom_commands = Blueprint('custom_commands', __name__)

@custom_commands.app_template_global()
def reverse_word(word):
    reversed_word = word[::-1]
    return reversed_word
