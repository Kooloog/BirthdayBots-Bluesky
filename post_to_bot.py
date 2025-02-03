##########################################################################################
# This is the program that gets all the birthday info and makes a BlueSky post about it. #
##########################################################################################

import calendar
import datetime
import locale
import os
import PIL
import requests
import time

import secret

from atproto import Client, models
from atproto_client import SessionEvent, Session
from atproto_client.exceptions import BadRequestError
from atproto_core.exceptions import AtProtocolError
from PIL import Image

global client_acen, client_fe


# We start the BlueSky clients for each of the bots.
# Sessions for each bot are stored in separate .txt files. This way, only 1 login is needed, and not one per call.

# If the session of the AC bot is created or updated, this method will store the session that's been created or changed.
def on_session_change_acen(event: SessionEvent, session: Session):
    print('Session changed:', event, repr(session))
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        print('Saving changed session')
        save_session(session.export(), 'sessions/session_acen.txt')


# Same, but for the FE bot. We need one per bot, as this method is treated as a single argument, and it will always
# expect the same two arguments in its header (this is known as a callback function).
def on_session_change_fe(event: SessionEvent, session: Session):
    print('Session changed:', event, repr(session))
    if event in (SessionEvent.CREATE, SessionEvent.REFRESH):
        print('Saving changed session')
        save_session(session.export(), 'sessions/session_fe.txt')


# Gets the active session of a bot, if there is one.
def get_session(session_file):
    with open(session_file) as fi:
        return fi.read()


# Saves the newly created or updated session of the BlueSky account, if needed.
def save_session(session_string_save: str, session_file: str):
    with open(session_file, 'w') as fi:
        fi.write(session_string_save)


# Function to initialize the client (basically, makes the bot enter the BlueSky accounts as any normal user would
# do, by inputting both username and password to have access granted.
def init_client(session_file, session_user, session_pass):
    client = Client()
    if "acen" in session_file:
        client.on_session_change(on_session_change_acen)
    elif "fe" in session_file:
        client.on_session_change(on_session_change_fe)

    # On a successful login, the bot also returns a refresh token. As long as we have an active refresh token,
    # we can resume the session where we left it, and avoid having to log in with credentials again.
    session_string = get_session(session_file)
    if session_string:
        print('Reusing session')
        client.login(session_string=session_string)
    # The refresh token, however, expires after some time. In this case, we just log in the usual way.
    else:
        print('Creating new session')
        client.login(session_user, session_pass)

    return client


# Receives a month and a day as integers, and converts the date to a proper string like "July 13th" or "March 21st".
def get_day_string(_month, _day):
    date_end = "th"
    if _day == '1' or _day == '21' or _day == '31':
        date_end = "st"
    elif _day == '2' or _day == '22':
        date_end = "nd"
    elif _day == '3' or _day == '23':
        date_end = "rd"

    return calendar.month_name[int(_month)] + " " + str(_day) + date_end


def convert(birthday):
    # Pre-initialized variables, just so the code is clean and with no warnings.
    status = ""
    alt = ""
    aspect_ratio = ""
    completed = False
    posted = False

    # STEP 1: Generate the post's text, language depends on the bot. Also, the alt text for the image is made.
    if birthday[4] == 'ACEN' or birthday[4] == 'FE':
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        status = f"Today, {get_day_string(birthday[0], birthday[1])}, is {birthday[2]}'s{birthday[5]}birthday!"
        alt = '\n'.join(birthday[6].split('@'))

    # STEP 2: Get the post's image from Google Drive. The databases contain the link to each character's picture.
    img_url = f"https://drive.usercontent.google.com/download?id={birthday[3]}&authuser=0"
    attempt = 0

    # In case there are errors with Google Drive, the program will attempt to download the image once per minute
    # until it's successful, or until it's failed 10 times.
    while attempt < 10 and not completed:
        attempt += 1
        img_get = requests.get(img_url, stream=True)

        # A status code of 200 means the image was successfully downloaded
        if img_get.status_code == 200:
            with open('picture.png', 'wb') as out_file:
                out_file.write(img_get.content)

            # BlueSky returns a Timeout error for large files, so we reduce the image size in order to prevent it.
            try:
                image = Image.open('picture.png')
                newImage = image.resize((990, 540))
                newImage.save('picture.png')
                aspect_ratio = models.AppBskyEmbedDefs.AspectRatio(height=540, width=990)
                completed = True
            except PIL.UnidentifiedImageError:
                print("Error while reading the image (UnidentifiedImageError). Trying again...")
                time.sleep(5)
        # A status code other than 200 means there was an error of some kind in the download process.
        else:
            print(f"There has been an issue when downloading {birthday[2]}. Error code: {img_get.status_code}")
            time.sleep(60)
        del img_get

    # STEP 3: Post to BlueSky (with both text and media with ALT text) to the correct account.
    # Once again, the attempt loop is here in case there are capacity errors in the server.
    attempt = 0
    while attempt < 10 and not posted:
        try:
            attempt += 1
            with open('picture.png', 'rb') as img:
                # We transform the image into bytes that the BlueSky API can read, and send the post to
                # its respective bot. The bot a post belongs to is in the birthday array.
                img_data = img.read()
                if birthday[4] == 'ACEN':
                    client_acen.send_image(text=status, image=img_data, image_alt=alt, image_aspect_ratio=aspect_ratio)
                    posted = True
                elif birthday[4] == 'FE':
                    client_fe.send_image(text=status, image=img_data, image_alt=alt, image_aspect_ratio=aspect_ratio)
                    posted = True

        # Catches an error if the image has failed to download, and ends the program.
        except OSError as err:
            print("An error has occurred while loading the file.\nTrace: ", err)
            continue
        # Catches an error if there was a problem with BlueSky, waits a minute, then tries again.
        except AtProtocolError as err:
            print("The POST request has failed. The program will try again in one minute.\nTrace: ", err)
            time.sleep(60)

    # Once it's posted, we don't want to store the post's image locally, so we delete it.
    os.remove('picture.png')


def main():
    try:
        # The global variables are loaded so this assignation stays at any point during the execution.
        global client_acen
        global client_fe
        client_acen = init_client('sessions/session_acen.txt', secret.acen_username, secret.acen_password)
        client_fe = init_client('sessions/session_fe.txt', secret.fe_username, secret.fe_password)
    except BadRequestError:
        # Sometimes, the bot's access and refresh tokens may expire. In such cases, the program forces a new
        # login by erasing all session info, then trying to execute the program from the beginning.
        print("BadRequestError, emptying files and retrying...")
        open('sessions/session_acen.txt', 'w').close()
        open('sessions/session_fe.txt', 'w').close()
        main()
        return

    # Main code starts here.
    day = datetime.date.today().day
    month = datetime.date.today().month
    date_to_find = str(month) + "|" + str(day) + "|"
    print(date_to_find)

    # With the current day and month stored, the program will search in all databases for the characters whose birthday
    # is today. To do this, it seeks lines starting with "month|day". For example, 4|22 represents April 22nd.
    for file in os.listdir("databases"):
        database = open('databases/' + file, "r", encoding="utf8")
        for line in database:
            if line.startswith(date_to_find):
                # If these lines are executed, it means the program has found a character with their birthday being
                # the current day. Character data is converted to an array, then passed to the convert function.
                found = line.split('|')
                convert(found)
                time.sleep(10)  # Cool-down so that BlueSky does not think I'm running a spam bot.
