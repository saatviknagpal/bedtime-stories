from story.llm import call_model
from story.prompts import STORYTELLER_SYSTEM

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""

example_requests = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."


def main():
    user_input = input("What kind of story do you want to hear? ")
    print(call_model(user_input, system=STORYTELLER_SYSTEM))


if __name__ == "__main__":
    main()
