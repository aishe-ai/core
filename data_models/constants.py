LOADING_INDICATOR = "Loading...."
LOADING_BLOCK = [
    {
        "type": "section",
        "text": {"type": "mrkdwn", "text": LOADING_INDICATOR},
        # "accessory": {
        #     "type": "image",
        #     "image_url": "https://media.tenor.com/UnFx-k_lSckAAAAM/amalie-steiness.gif",
        #     "alt_text": "loading spinner",
        # },
    }
]
CUSTOM_SLACK_COMMANDS = ["/intragpt-health-check"]

EXAMPLE_PROMPTS = [
    "- Normal prompts like in chatgpt:\n\t\t\t- Who is Sam Hyde?",
    "- Google:\n\t\t\t- Wie hoch ist die Regenwahrscheinlichkeit heute in Hannover?\n\t\t\t- Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?",
    "- Website:\n\t\t\t- Wo kann ich auf dieser Website meine Fragen einreichen? https://verwaltung.bund.de/portal/DE/ueber\n\t\t\t- Wann endet die Frist für die erste Phase? https://verwaltung.bund.de/leistungsverzeichnis/de/leistung/99148138017000",
    "- Documents (with attached file):\n\t\t\t- Summarize this document\n\t\t\t- Translate this file into german\n\n"
    "- Confluence:\n\t\t\t- Summarize the page: https://...... \n\n"
    "- Git repos:\n\t\t\t- In which language is this project written: https://github.com/martinmimigames/little-music-player?\n\t\t\t- What does HWListener in this project https://github.com/martinmimigames/little-music-player do?\n\t\t\t- What is the difference of the m3u branch in this project: https://github.com/martinmimigames/little-music-player?\n\n",
    "- Image Generation with DALL-E:\n\t\t\t- Create an image of a space mountain",
]

# Tuple of top 50+ most used programming language file extensions, including all Elixir extensions
ALLOWED_FILE_EXTENSIONS = (
    ".java",
    ".py",
    ".c",
    ".cpp",
    ".js",
    ".html",
    ".css",
    ".php",
    ".cs",
    # ".rb",
    ".go",
    ".swift",
    ".ts",
    # ".r",
    ".sh",
    # ".pl",
    # ".m",
    ".sql",
    # ".kt",
    # ".rs",
    # ".groovy",
    ".lua",
    ".vb",
    # ".f",
    # ".s",
    # ".asm",
    # ".dart",
    # ".hs",
    # ".pas",
    # ".elm",
    # ".clj",
    # ".erl",
    # ".ada",
    # ".cob",
    # ".lisp",
    ".scm",
    # ".rkt",
    # ".d",
    # ".jl",
    ".ex",
    ".exs",
    ".eex",
    ".leex",
    ".heex",
    # ".f90",
    # ".cr",
    # ".nim",
    # ".v",
    # ".h",
    # ".hpp",
    # ".hxx",
    ".ipynb",
    # ".md",
)
