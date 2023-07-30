# tg_aggregator-
Это данные акка.

![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/6bb5d261-d1ee-48bb-83bb-d6789d737755)

Вот эти три получешь здесь при регистрации приложения https://core.telegram.org/api/obtaining_api_id

    API_ID
    API_HASH
    BOT_TOKEN


По сути он принимает зарегестрированный аккаунт в телеграмме. Это может быть фейк или личный аккаунт.
Свой номер лучше не вводить, там тогда выходит из всех приложений.
Указываешь номер, где phone. Подключаешься через метод     

    async def start(self) -> None:
            await self.client.start()
            
При инициализации он запрашивает пароль от акка.

    
    Я взял акк здесь. Там же после покупки можно скачать сразу файл .session.
    https://lzt.market/
    

Он создает сессию (файлик .session) в формате SQlite.
Здесь лежит сессия.
![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/d2c2c6b0-ad64-47ee-ac48-4ba1b0df148a)


![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/7b180ea3-cd92-4ff1-9593-5c2ed55fc1e4)

    async def main(channel: Union[str, int]) -> tuple[str, int, int, list]: 
    Принимает id или имя канала (группы). 
    Когда копируешь имя в телеге получешь формат URLа https://t.me/fastapiru. 
    Нужно оставить только путь, то есть fastapiru

    parser = ChannelParser(API_ID, API_HASH, PHONE, BOT_TOKEN) Создаем парсер. 
    В инициализацию передаем идентификационные данные.

    parser.client = 'telethon' Здесь можно любое имя писать, 
    но сессия будет по новой активироваться с вводом пароля от акка.
    
    await parser.start() Стартуем, если нет привязанной сессии, 
    то запросит пароль и создат файл сессии
    
    await parser.join_channel(channel) Вступает в группу. 
    Вообще поведение и возможности абсолютно идентичны 
    пользователю телеграмма (этот то же клиентское приложение, только с некой логикой внутри)
    
    channel_instance = await parser.get_all_participants(channel) Получаем результаты
![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/15e47804-425b-4330-a685-bc6bd1ce721f)

Если акк уже вступил в группу, лучше закоментить строку 

      # await parser.join_channel(channel)
      
Один акк так уже заблокировали.

Здесь вводим саму группу или канал.

![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/27b422fb-aba0-47ce-98b3-a84f62621a94)



Здесь основная логика. Так как каналы и группы имеют разные интерфейсы, то идет определение что это.За это отвечает entity.broadcast.
![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/135073bd-be95-40b8-8067-a9b88170fe34)



Для каналов получение пользователей немного сложнее по логике. limit это размер чанка, который выдаст генератор. 

Группы:

    get_chunked_participants Я постаивл 5000, но если канал больше пользователь имеет,
    можно и больше постаивть. Ограничений я пока что не увидел.
    get_comments_from_chat Аналогично ограничений не увидел. 


Каналы:

    get_comments_from_channel
    get_messages Поставил 50, также можно что угодно выставлять, 
    это получение сообщений из чатов в канале 

Само собой, чем больше данных нужно выгрузить, тем дольше будет работать. Но в целом все очень быстро происходит. Сам фреймворк нативно ассинхронный.

![image](https://github.com/leonidsliusar/tg_aggregator-/assets/128726342/9a5dc33c-97d8-4bd4-868e-73b3a4def3ff)


логин и пароль от субд задается в окружении docker-compose
    environment:
      - NEO4J_AUTH=neo4j/difficulties-pushup-gaps

web интерфейс субд здесь авторизация с теми же данными
        
    http://localhost:7474/browser/

Запустить можно из main.py передав в метод load_data id или название группы/канала
    
    asyncio.run(DataManager.load_data('<channel>'))

Выгрузить данные передав в метод get_data один из ключей словаря query_dict db/queries.py, по дефолту выгружает 
в хеш мапу (dict), аргументом n передать целочисленное значение(если необходимо для запроса), 
можно передать аргументом out_type тип выгрузки table, dframe (нужен pandas для обработки), dict.

    asyncio.run(DataManager.get_data(<commad: str>, <n: int>, <out_type: str>))

