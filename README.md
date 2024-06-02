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

Groupint is powered by [Telesint](https://telesint.dev/en/), a database of over 3 million open Telegram chats and tens of thousands of private chats. When you log in to Groupint, you are required to set up a session with Telesint to access data on Telegram groups. Provide your ``phone number``, ``API id`` and ``API hash`` and create your session.

Acquire the  ``API id`` and ``API hash`` from [Telegram](https://core.telegram.org/api/obtaining_api_id). You need to do the following:
1. Sign up for Telegram
2. Log in to your Telegram account [https://my.telegram.org](https://my.telegram.org/).
3. Got to ["API development tools"](https://my.telegram.org/apps) and fill out the form
4. You will get your ``API id`` and ``API hash`` parameters required for user authorization.
5. For the moment, each number can only have one api id connected to it. 

### Prerequisites

1.  Docker to compose the project
    
2.  Python 3.11
    
3.  Poetry to install python dependencies and set up your virtual environment
   

###  Clone project and start the containers (docker compose or docker-compose)

 Clone the Groupint project from the OSINT for Ukraine Githubaccount, set inline variables and run docker-compose to set up the project . 
```
git clone https://github.com/OSINT-for-Ukraine/groupint.git
cd groupint
docker-compose up
```
###  Set log in

Next step is to set your app's password. Create a  ``secrets.toml`` file inside the streamlit folder and set your password.
```
# Create secrets file 
cd streamlit 
touch secrets.toml
# Set password variable
password = "xxxx"
```
###  Run Groupint

Make sure you have python3.11, a virtual environment, and poetry to install dependencies and run the project. To run the app:
```
streamlit run interface.py
```


## Licensing

Groupint is the exclusive property of OSINT for Ukraine and is distributed under xxxx


## Support and Contact

Users experiencing technical issues or bugs can report them through the designated issue reporting system on the OSINT for Ukraine GitHub repository.


## Community Engagement

Stay connected with the OSINT for Ukraine community to receive updates, participate in discussions, and contribute to the ongoing development of Groupint. Engage through forums, social media, and other community channels.

Thank you for using Groupint, contributing to OSINT for Ukraine's mission to enhance information analysis and transparency.
