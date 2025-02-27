URL: https://github.com/sparfenyuk/mcp-telegram/blob/main/src/mcp_telegram/telegram.py
---
[Skip to content](https://github.com/sparfenyuk/mcp-telegram/blob/main/src/mcp_telegram/telegram.py#start-of-content)

You signed in with another tab or window. [Reload](https://github.com/sparfenyuk/mcp-telegram/blob/main/src/mcp_telegram/telegram.py) to refresh your session.You signed out in another tab or window. [Reload](https://github.com/sparfenyuk/mcp-telegram/blob/main/src/mcp_telegram/telegram.py) to refresh your session.You switched accounts on another tab or window. [Reload](https://github.com/sparfenyuk/mcp-telegram/blob/main/src/mcp_telegram/telegram.py) to refresh your session.Dismiss alert

[sparfenyuk](https://github.com/sparfenyuk)/ **[mcp-telegram](https://github.com/sparfenyuk/mcp-telegram)** Public

- [Notifications](https://github.com/login?return_to=%2Fsparfenyuk%2Fmcp-telegram) You must be signed in to change notification settings
- [Fork\\
3](https://github.com/login?return_to=%2Fsparfenyuk%2Fmcp-telegram)
- [Star\\
15](https://github.com/login?return_to=%2Fsparfenyuk%2Fmcp-telegram)


## Files

main

/

# telegram.py

Copy path

Blame

Blame

## Latest commit

[![sparfenyuk](https://avatars.githubusercontent.com/u/134065?v=4&size=40)](https://github.com/sparfenyuk)[sparfenyuk](https://github.com/sparfenyuk/mcp-telegram/commits?author=sparfenyuk)

[fix: store session in xdg-state-home](https://github.com/sparfenyuk/mcp-telegram/commit/ce8220d22157ce441cf45abc7de1d090555638ae)

Dec 13, 2024

[ce8220d](https://github.com/sparfenyuk/mcp-telegram/commit/ce8220d22157ce441cf45abc7de1d090555638ae) · Dec 13, 2024

## History

[History](https://github.com/sparfenyuk/mcp-telegram/commits/main/src/mcp_telegram/telegram.py)

66 lines (53 loc) · 2.11 KB

/

# telegram.py

Top

## File metadata and controls

- Code

- Blame


66 lines (53 loc) · 2.11 KB

[Raw](https://github.com/sparfenyuk/mcp-telegram/raw/refs/heads/main/src/mcp_telegram/telegram.py)

1

2

3

4

5

6

7

8

9

10

11

12

13

14

15

16

17

18

19

20

21

22

23

24

25

26

27

28

29

30

31

32

33

34

35

36

37

38

39

40

41

42

43

44

45

46

47

48

49

50

51

52

53

54

55

56

57

58

59

60

61

62

63

64

65

66

\# ruff: noqa: T201

from \_\_future\_\_ importannotations

fromfunctoolsimportcache

fromgetpassimportgetpass

frompydantic\_settingsimportBaseSettings

fromtelethonimportTelegramClient\# type: ignore\[import-untyped\]

fromtelethon.errors.rpcerrorlistimportSessionPasswordNeededError\# type: ignore\[import-untyped\]

fromtelethon.tl.typesimportUser\# type: ignore\[import-untyped\]

fromxdg\_base\_dirsimportxdg\_state\_home\# type: ignore\[import-error\]

classTelegramSettings(BaseSettings):

api\_id: str

api\_hash: str

classConfig:

env\_prefix="TELEGRAM\_"

env\_file=".env"

asyncdefconnect\_to\_telegram(api\_id: str, api\_hash: str, phone\_number: str) ->None:

user\_session=create\_client(api\_id=api\_id, api\_hash=api\_hash)

awaituser\_session.connect()

result=awaituser\_session.send\_code\_request(phone\_number)

code=input("Enter login code: ")

try:

awaituser\_session.sign\_in(

phone=phone\_number,

code=code,

phone\_code\_hash=result.phone\_code\_hash,

)

exceptSessionPasswordNeededError:

password=getpass("Enter 2FA password: ")

awaituser\_session.sign\_in(password=password)

user=awaituser\_session.get\_me()

ifisinstance(user, User):

print(f"Hey {user.username}! You are connected!")

else:

print("Connected!")

print("You can now use the mcp-telegram server.")

asyncdeflogout\_from\_telegram() ->None:

user\_session=create\_client()

awaituser\_session.connect()

awaituser\_session.log\_out()

print("You are now logged out from Telegram.")

@cache

defcreate\_client(

api\_id: str\|None=None,

api\_hash: str\|None=None,

session\_name: str="mcp\_telegram\_session",

) ->TelegramClient:

ifapi\_idisnotNoneandapi\_hashisnotNone:

config=TelegramSettings(api\_id=api\_id, api\_hash=api\_hash)

else:

config=TelegramSettings()

state\_home=xdg\_state\_home() /"mcp-telegram"

state\_home.mkdir(parents=True, exist\_ok=True)

returnTelegramClient(state\_home/session\_name, config.api\_id, config.api\_hash, base\_logger="telethon")

You can’t perform that action at this time.