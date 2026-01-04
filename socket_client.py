import socketio

sio_client = socketio.AsyncClient()

async def connect_socket():
    if not sio_client.connected:
        await sio_client.connect("http://localhost:5000?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJZb3VyLUlzc3VlciIsImlhdCI6MTc2NzQzNDc1Ny4yMTQ0MzgsInN1YiI6IntcInVzZXJfaWRcIjogMTAsIFwiZW1haWxcIjogXCJqaGFudmlqb3NoaTIxOThAZ21haWwuY29tXCIsIFwidXNlcl90eXBlXCI6IFwiY3VzdG9tZXJcIn0ifQ.557HlZuQdjDK9iECH2xc_zaT7XunwQI9k31Pm_wMImI")

