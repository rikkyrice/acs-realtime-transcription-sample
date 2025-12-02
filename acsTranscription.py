import json

class ACSTranscriptionHandler:
    transcription_websocket = None

    def __exit__(self, exc_type, exc_value, traceback):
        self.transcription_websocket.close()

    #init_websocket -> init_transcription_websocket (transcription)
    async def init_transcription_websocket(self, socket):
        # print("--inbound socket set")
        self.transcription_websocket = socket

    async def handle_transcription(self, stream_data):
        try:
            data = json.loads(stream_data)
            kind = data['kind']
            if kind == "TranscriptionData":
                transcription_data_section = data.get("transcriptionData", {})
                transcription_data = transcription_data_section.get("text")
                print(f" User (ai speech):-- {transcription_data}")
        except Exception as e:
            print(f'Error processing WebSocket message: {e}')
