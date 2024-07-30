import praw
import requests
import json
import os
import re
import logging
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
import argparse

load_dotenv()  # take environment variables from .env.

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Process Reddit posts.')
parser.add_argument('--method', type=str, default='chat', choices=['translate', 'chat'],
                    help='Method to use for processing text. "translate" uses Deepl, "chat" uses GPT-3.5 Turbo.')
parser.add_argument('--lang', type=str, default='EN',
                    help='Target language for translation. Only used if method is "translate".')
args = parser.parse_args()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat_with_gpt3(prompt):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an assistant that processes English Reddit post text.  You search the post text  looking for stories to optimize for text-to-speech.  The writer of the post tends to jump between talking to the audience about reddit and then will jump back into telling a story without proper story structure so the post content will need to refactored.  Analyze the text and refactor it into fluent stories suitable for text-to-speech while excluding any content that addresses the audience directly about reddit or the post itself.  Keep each story's content as intact as possible while optimizing for text-to-speech.  Provide a title for each story, but do not number them or encapsulate them with special characters.  Do not summarize the stories with a conclusion paragraph."},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Error processing text with GPT-40-mini: {e}")
        return None

def get_reddit_post(url):
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
        )
        post = reddit.submission(url=url)
        return post.title, post.selftext
    except Exception as e:
        logging.error(f"Error fetching Reddit post: {e}")
        return None, None

def translate_text(text, target_lang):
    try:
        url = "https://api-free.deepl.com/v2/translate"
        data = {
            "auth_key": os.getenv("DEEPL_AUTH_KEY"),
            "text": text,
            "target_lang": target_lang,
        }
        response = requests.post(url, data=data)
        response_json = response.json()
        return response_json['translations'][0]['text']
    except Exception as e:
        logging.error(f"Error translating text: {e}")
        return None

def modify_json(title_text, part_text, outro_text, main_text):
    data = []
    for i in range(len(title_text)):
        data.append({
            "series": title_text[i],
            "part": part_text[i],
            "outro": outro_text[i],
            "text": main_text[i]
        })

    with open('./video.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

def read_file_line_by_line(file_path):
    try:
        with open(file_path, 'r') as file:
            for line in file:
                yield line
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")

def main():
    title_text = []
    main_text = []

    lines = list(read_file_line_by_line('./reddit-post.txt'))

    for line in tqdm(lines, desc="Processing Reddit posts", unit="post"):
        title, text = get_reddit_post(line.strip())
        if title is None or text is None:
            continue

        if args.method == 'translate':
            text = translate_text(text, args.lang)
        elif args.method == 'chat':
            text = chat_with_gpt3(text)

        if text is None:
            continue

        # Clean and modify text
        for pattern in [(r'\\n\\n', '.'), (r'&#x200B', ''), (r'\\(\\d+\\s*[mwMW]\\)?', ''), (r'\\(\\s*[mwMW]\\s*\\d+\\)?', ''), (r'[<>:"/\\\\|?*,]', '')]:
            title = re.sub(pattern[0], pattern[1], title)
            text = re.sub(pattern[0], pattern[1], text)

        title_text.append(title)
        main_text.append(text)

    part_text = [""] * len(title_text)
    outro_text = [""] * len(title_text)

    modify_json(title_text, part_text, outro_text, main_text)

if __name__ == "__main__":
    main()
