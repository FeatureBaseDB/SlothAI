from flask import Blueprint, render_template
from flask import current_app as app
from faker import Faker

custom_commands = Blueprint('custom_commands', __name__)

@custom_commands.app_template_global()
def reverse_word(word):
    reversed_word = word[::-1]
    return reversed_word

@custom_commands.app_template_global()
def random_word():
    fake = Faker()
    return fake.word()


@custom_commands.app_template_global()
def random_sentence():
    fake = Faker()
    return fake.sentence()