<p align="center">


  <h3 align="center">📡 Groupint</h3>

  <p align="center">
    An OSINT tool to identify actors and networks on Telegram
   
  </p>
</p>

<!-- TABLE OF CONTENTS 
<details open="open">
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#Groupint">Groupint</a>
    </li>
    <li><a href="#About OSINT for Ukraine">About OSINT for Ukraine</a>
    </li>
     <li><a href="#About OSINT for Ukraine">Get started</a>
    </li>
     </li>
     <li><a href="#About OSINT for Ukraine">License</a>
    </li>
     </li>
     <li><a href="#About OSINT for Ukraine">Support & Contact</a>
      </li>
     <li><a href="#About OSINT for Ukraine">Community Engagement</a>
    </li>
    </li>
  </ol>
</details>
-->


# Groupint

Groupint is an application developed by OSINT for Ukraine that enables investigators to scrape data from Telegram groups and connect “who’s talking to whom” through an intuitive and visually appealing graph user interface.

This tool empowers investigators to analyse networks within specific Telegram communities.

## About OSINT for Ukraine

[OSINT for Ukraine](https://www.osintforukraine.com/) is an independent non-profit foundation dedicated to using open-source intelligence to investigate international war crimes in relation to the Russo-Ukrainian war, Research Influence and Disinformation operations in Europe, and to provide OSINT and OPSEC advisory and training.
  
Headquartered in The Hague, we are a multinational team of professionals with experience in OSINT investigations, human rights law, and investigative journalism. Our Research and Development team is dedicated to developing full spectrum OSINT solutions in the pursuit of justice, truth, memory.

## Get started

### Acquire API credentials

Groupint uses your own Telegram account (via [Telethon](https://docs.telethon.dev/)) to scrape group members and stores results in Neo4j for graph analysis.

Acquire your ``API id`` and ``API hash`` from [Telegram](https://core.telegram.org/api/obtaining_api_id). You need to do the following:
1. Sign up for Telegram
2. Log in to your Telegram account [https://my.telegram.org](https://my.telegram.org/).
3. Got to ["API development tools"](https://my.telegram.org/apps) and fill out the form
4. You will get your ``API id`` and ``API hash`` parameters required for user authorization.
5. For the moment, each number can only have one api id connected to it. 

### Prerequisites

1.  Docker to compose the project
    
2.  Python 3.11
    
3.  Poetry to install python dependencies and set up your virtual environment

4.  [Pre-commit](https://pre-commit.com/) for linters and codestyle.
   ```
pip install pre-commit
pre-coomit instal
   ```
   

###  Clone project and start the containers (docker compose or docker-compose)

 Clone the Groupint project from the OSINT for Ukraine Githubaccount, set inline variables and run docker-compose to set up the project . 

```
git clone https://github.com/OSINT-for-Ukraine/groupint.git
cd groupint
docker-compose up
```
###  Telegram defaults (optional)

Default phone, API id, and API hash are read from ``.streamlit/secrets.toml``:

```toml
[telegram]
phone = "+351966750855"
api_id = "38530306"
api_hash = "your_api_hash"
```

Edit this file to change defaults. The app does not use a separate Streamlit password gate.
###  Run Groupint

Make sure you have python3.11, a virtual environment, and poetry to install dependencies and run the project. To run the app:
```
streamlit run interface.py
```

###  Commiting your changes

If you want to enhance groupint by providing your fixes simply 
1. Create a new branch, with a name related to your change.
2. Modify the repo with your changes
3. Commit your change
  - Choose a meaningful description of your commit
  - Pre-commit is gonna run static code analysis of your changes.
    - Either your code will be changed automatically to be compliant
    - Or you will get guidelines on what you should change.
4. Push
5. Create a PR to the main branch
  - If there is a job triggered by your change it has to complete succsessfuly, you can check the output of the job to see why it failed
  - Someone need to review your change and mark it as correct
  - If both conditions above are fulfilled, your change will be merged.
   

## Licensing

Groupint is distributed under the [General Public License (GPL)](https://www.gnu.org/licenses/agpl-3.0.en.html). You are free to use, distribute, and change the software. Any modified version must also be distributed under the GPL.


## Support and Contact

Users experiencing technical issues or bugs can report them through the designated issue reporting system on the OSINT for Ukraine GitHub repository.


## Community Engagement

Stay connected with the OSINT for Ukraine community to receive updates, participate in discussions, and contribute to the ongoing development of Groupint. Engage through forums, social media, and other community channels.

- [Linkedin](https://www.linkedin.com/company/osint-for-ukraine/mycompany/)
- [Instagram](https://www.instagram.com/osintforukraine/) - @osintforukraine
- [Linktree](https://linktr.ee/osintforukraine)
- [YouTube](https://www.youtube.com/@OSINTFORUKRAINE)


Thank you for using Groupint, contributing to OSINT for Ukraine's mission to enhance information analysis and transparency.
