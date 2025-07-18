# import requests

# def reverse_geocode(lat, lon):
#     import pdb;pdb.set_trace()  # Debugging line to inspect variables
#     url = "https://nominatim.openstreetmap.org/reverse"
#     params = {
#         'format': 'json',
#         'lat': lat,
#         'lon': lon,
#         'zoom': 18,
#         'addressdetails': 1
#     }
#     headers = {
#         'User-Agent': 'YourAppName/1.0 (your.email@example.com)'
#     }

#     response = requests.get(url, params=params, headers=headers)
    
#     if response.status_code == 200:
#         data = response.json()
#         return data.get("display_name", "Address not found")
#     else:
#         return f"Error: {response.status_code}"

# # Ride location
# ride_lat, ride_lon = 19.0271, 72.8381
# ride_address = reverse_geocode(ride_lat, ride_lon)
# print("Ride Address:", ride_address)

# # Driver location
# driver_lat, driver_lon = 19.1235, 72.1235
# driver_address = reverse_geocode(driver_lat, driver_lon)
# print("Driver Address:", driver_address)


from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import json

app = FastAPI(title="Reverse Geocoding API", version="1.0")

@app.get("/reverse-geocode")
async def hello():
    res = {"name": "janvi", "age": 20}
    return JSONResponse(content=res)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)