import asyncio



async def download_users_file(client, channel, button_index):
    '''
    We want users to download a copy of user data in JSON and XLSX. Users can only download JSON once/day with premium but xlsx is always available. 

    '''
    await client.send_message(entity="telesint_bot", message=channel)
    await asyncio.sleep(5)
    async for message in client.iter_messages(entity="telesint_bot", limit=1):
        if message.buttons:
            
            #Download XSLX/JSON
            await message.click(button_index)
            await asyncio.sleep(10)
            
            #Confirm Yes button
            await message.click(0)
            await asyncio.sleep(10)


            while True:
                async for message in client.iter_messages(entity="telesint_bot", limit=1):
                    if message.media:
                        file_path = await message.download_media(file="download_files")
                        file_name = file_path
                        return file_path, file_name
                     

                await asyncio.sleep(5)
    return None



