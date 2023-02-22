import sys
import asyncio
import websockets
import json
import curses
import time

from changes import apply_changes

################
## UTILS
################

def usage():
    return f"Usage: {sys.argv[0]} " + "{port} {match_name} {display}"

################
## FUNCTIONS
################

#### GLOBAL ####
match = None
################

async def hello(ws):
    hello_msg = {
        "type": "hello",
        "username": "anonymous"
    }
    await ws.send(json.dumps(hello_msg))
    ans = {}
    while "type" not in ans or ans["type"] != "hello":
        ans = await ws.recv()
        ans = json.loads(ans)
    if "errors" in ans or not ans["success"]:
        print(f'Error: Authorization error - {ans["errors"]}')
        exit(1)
    return ans["newUsername"]

async def schema_match(ws, match_name):
    schema_msg = {
        "type": "schema",
        "name": match_name
    }
    await ws.send(json.dumps(schema_msg))
    ans = {}
    while "type" not in ans or ans["type"] != "schema":
        ans = await ws.recv()
        ans = json.loads(ans)
    if "errors" in ans or not "schema" in ans:
        print(f'Error: {ans["errors"]}')
        exit(1)
    return ans["schema"]

async def get_match(ws, match_name):
    get_msg = {
        "type": "get",
        "name": match_name
    }
    await ws.send(json.dumps(get_msg))
    ans = {}
    while "type" not in ans or ans["type"] != "get":
        ans = await ws.recv()
        ans = json.loads(ans)
    if "errors" in ans or not "value" in ans:
        print(f'Error: {ans["errors"]}')
        exit(1)
    return ans["value"], ans["lastChangeId"] if "lastChangeId" in ans else None, ans["lastChangeAt"] if "lastChangeAt" in ans else None

async def subscribe_match(ws, match_name, last_change_at, last_change_id):
    subscribe_msg = {
        "type": "subscribe",
        "name": match_name
    }
    if last_change_at is not None:
        subscribe_msg["lastChangeAt"] = last_change_at
    if last_change_id is not None:
        subscribe_msg["lastChangeId"] = last_change_id 
    await ws.send(json.dumps(subscribe_msg))
    ans = {}
    while "type" not in ans or ans["type"] != "subscribe":
        ans = await ws.recv()
        ans = json.loads(ans)
    if "errors" in ans or not "success" in ans:
        print(f'Error: {ans["errors"]}')
        exit(1)
    return ans["success"]

def draw_match_status(stdscr, m, last_changes):
    # Clear screen
    stdscr.clear()

    match_info = m["matchInfo"]
    match_data = m["matchData"]

    # Match info
    stdscr.addstr(f'----------------------------------\n')
    stdscr.addstr(f'-------------- INFO --------------\n')
    stdscr.addstr(f'----------------------------------\n')
    stdscr.addstr(f'Datetime: {match_info["date"][:-1]} {match_info["time"][:-1]}\n')
    stdscr.addstr(f'\n')
    stdscr.addstr(f'|{match_data["scores"]["total"]["home"]}| - [{match_info["contestant"][0]["code"]}] {match_info["contestant"][0]["officialName"]}\n')
    stdscr.addstr(f'VS\n')
    stdscr.addstr(f'|{match_data["scores"]["total"]["away"]}| - [{match_info["contestant"][1]["code"]}] {match_info["contestant"][1]["officialName"]}\n')
    stdscr.addstr(f'\n')
    stdscr.addstr(f'Stadium: {match_info["venue"]["longName"]}\n')
    stdscr.addstr(f'----------------------------------\n')
    stdscr.addstr(f'\n')

    # Match data
    stdscr.addstr(f'----------------------------------\n')
    stdscr.addstr(f'-------------- DATA --------------\n')
    stdscr.addstr(f'----------------------------------\n')
    if match_data["status"] == "playing":
        periods = match_data["period"]
        if len(periods) == 1:
            if not match_data["overtime"]:
                stdscr.addstr(f'Status: Playing - First Half\n')
            else:
                stdscr.addstr(f'Status: Playing - First Half - Overtime\n')
        else:
            if not match_data["overtime"]:
                stdscr.addstr(f'Status: Playing - Second Half\n')
            else:
                stdscr.addstr(f'Status: Playing - Second Half - Overtime\n')
    elif match_data["status"] == "halftime":
        stdscr.addstr(f'Status: Half Time\n')
    elif match_data["status"] == "finished":
        stdscr.addstr(f'Status: Finished\n')
    stdscr.addstr(f'Match time: {match_data["lengthMin"]:02d}:{match_data["lengthSec"]:02d}\n')
    stdscr.addstr(f'----------------------------------\n')

    # Refresh screen
    stdscr.refresh()

async def observe_match(match_name, port, display):
    global match

    async with websockets.connect("ws://localhost:" + str(port)) as ws:
        print("Connection successfull")

        username = await hello(ws)
        print(f"Client username: {username}")

        match, last_change_at, last_change_id = await get_match(ws, match_name)
        sub = await subscribe_match(ws, match_name, last_change_at, last_change_id)
        if not sub:
            print("Error while subscribing")
            exit(1)
        print(f"Subscribed: {sub}")

        if display:
            stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            curses.curs_set(0)
        while match and "matchData" in match and "status" in match["matchData"] and match["matchData"]["status"] != "finished":
            msg = await ws.recv()
            msg = json.loads(msg)
            if "errors" in msg:
                print(f'There has been an error: {msg["errors"]}')
                break
            if "type" in msg and msg["type"] == "changes":
                # do sth
                changes = msg["changes"]
                apply_changes(match, msg["changes"])
                if display:
                    draw_match_status(stdscr, match, changes)
                pass
        if display:
            time.sleep(3)
            curses.echo()
            curses.nocbreak()
            curses.endwin()

        print("Connection finished")
        print(match["matchData"]["lineUp"][1]["players"][0])

################
## MAIN
################

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Error: missing arguments")
        print(usage())
        exit(1)
    
    port       = int(sys.argv[1])
    match_name = sys.argv[2]
    display    = sys.argv[3].lower() == "true"

    asyncio.run(observe_match(match_name, port, display))