######################################################################################
# This is the program that the server executing this software is constantly running. #
######################################################################################

import time
import schedule

import post_to_bot


# Very simple function that simply runs the important code
def run_code():
    post_to_bot.main()


# This line executes the above function every day at 2pm CEST (my timezone)
schedule.every().day.at("13:00").do(run_code)

# And now we wait :)
while True:
    schedule.run_pending()
    time.sleep(5)
