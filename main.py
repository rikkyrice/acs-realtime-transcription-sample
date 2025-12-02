from quart import Quart, Response, request, json, websocket
from azure.eventgrid import EventGridEvent, SystemEventNames
from urllib.parse import urlencode, urlparse, urlunparse
from logging import INFO
from azure.communication.callautomation import (
    MediaStreamingOptions,
    AudioFormat,
    MediaStreamingContentType,
    MediaStreamingAudioChannelType,
    StreamingTransportType,
    TranscriptionOptions,
    )
from azure.communication.callautomation.aio import (
    CallAutomationClient
    )
import uuid

from azureOpenAIService import OpenAIRTHandler
from acsTranscription import ACSTranscriptionHandler

# Your ACS resource connection string
ACS_CONNECTION_STRING = "ACS_CONNECTION_STRING"

# Callback events URI to handle callback events.
CALLBACK_URI_HOST = "CALLBACK_URI_HOST"
CALLBACK_EVENTS_URI = CALLBACK_URI_HOST + "/api/callbacks"

# Cognitive Services Endpoint and key
COGNITIVE_SERVICES_ENDPOINT = "COGNITIVE_SERVICES_ENDPOINT"

acs_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)
app = Quart(__name__)

@app.route("/api/incomingCall",  methods=['POST'])
async def incoming_call_handler():
    app.logger.info("incoming event data")
    for event_dict in await request.json:
            event = EventGridEvent.from_dict(event_dict)
            app.logger.info("incoming event data --> %s", event.data)
            if event.event_type == SystemEventNames.EventGridSubscriptionValidationEventName:
                app.logger.info("Validating subscription")
                validation_code = event.data['validationCode']
                validation_response = {'validationResponse': validation_code}
                return Response(response=json.dumps(validation_response), status=200)
            elif event.event_type =="Microsoft.Communication.IncomingCall":
                app.logger.info("Incoming call received: data=%s", 
                                event.data)  
                if event.data['from']['kind'] =="phoneNumber":
                    caller_id =  event.data['from']["phoneNumber"]["value"]
                else :
                    caller_id =  event.data['from']['rawId'] 
                app.logger.info("incoming call handler caller id: %s",
                                caller_id)
                incoming_call_context=event.data['incomingCallContext']
                guid =uuid.uuid4()
                query_parameters = urlencode({"callerId": caller_id})
                callback_uri = f"{CALLBACK_EVENTS_URI}/{guid}?{query_parameters}"
                
                parsed_url = urlparse(CALLBACK_EVENTS_URI)
                websocket_url = urlunparse(('wss',parsed_url.netloc,'/ws','', '', ''))
                transcription_websocket_url = urlunparse(('wss',parsed_url.netloc,'/transcriptionws','', '', ''))

                app.logger.info("callback url: %s",  callback_uri)
                app.logger.info("websocket url: %s",  websocket_url)
                app.logger.info("transcription websocket url: %s",  transcription_websocket_url)

                transcription_options = TranscriptionOptions(
                    transport_url=transcription_websocket_url,
                    transport_type=StreamingTransportType.WEBSOCKET,
                    locale="ja-JP",
                    start_transcription=False)

                media_streaming_options = MediaStreamingOptions(
                        transport_url=websocket_url,
                        transport_type=StreamingTransportType.WEBSOCKET,
                        content_type=MediaStreamingContentType.AUDIO,
                        audio_channel_type=MediaStreamingAudioChannelType.UNMIXED,
                        start_media_streaming=True,
                        enable_bidirectional=True,
                        audio_format=AudioFormat.PCM24_K_MONO)
                
                answer_call_result = await acs_client.answer_call(incoming_call_context=incoming_call_context,
                                                            operation_context="incomingCall",
                                                            callback_url=callback_uri, 
                                                            media_streaming=media_streaming_options,
                                                            transcription=transcription_options,
                                                            cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT)
                app.logger.info("Answered call for connection id: %s",
                                answer_call_result.call_connection_id)
            return Response(status=200)

@app.route('/api/callbacks/<contextId>', methods=['POST'])
async def callbacks(contextId):
     for event in await request.json:
        # Parsing callback events
        global call_connection_id
        event_data = event['data']
        call_connection_id = event_data["callConnectionId"]
        app.logger.info(f"Received Event:-> {event['type']}, Correlation Id:-> {event_data['correlationId']}, CallConnectionId:-> {call_connection_id}")
        if event['type'] == "Microsoft.Communication.CallConnected":
            call_connection_properties = await acs_client.get_call_connection(call_connection_id).get_call_properties()
            media_streaming_subscription = call_connection_properties.media_streaming_subscription
            app.logger.info(f"MediaStreamingSubscription:--> {media_streaming_subscription}")
            app.logger.info(f"Received CallConnected event for connection id: {call_connection_id}")
            app.logger.info("CORRELATION ID:--> %s", event_data["correlationId"])
            app.logger.info("CALL CONNECTION ID:--> %s", event_data["callConnectionId"])
            await acs_client.get_call_connection(call_connection_id).start_transcription()
        elif event['type'] == "Microsoft.Communication.MediaStreamingStarted":
            app.logger.info(f"Media streaming content type:--> {event_data['mediaStreamingUpdate']['contentType']}")
            app.logger.info(f"Media streaming status:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatus']}")
            app.logger.info(f"Media streaming status details:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatusDetails']}")
        elif event['type'] == "Microsoft.Communication.MediaStreamingStopped":
            app.logger.info(f"Media streaming content type:--> {event_data['mediaStreamingUpdate']['contentType']}")
            app.logger.info(f"Media streaming status:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatus']}")
            app.logger.info(f"Media streaming status details:--> {event_data['mediaStreamingUpdate']['mediaStreamingStatusDetails']}")
        elif event['type'] == "Microsoft.Communication.MediaStreamingFailed":
            app.logger.info(f"Code:->{event_data['resultInformation']['code']}, Subcode:-> {event_data['resultInformation']['subCode']}")
            app.logger.info(f"Message:->{event_data['resultInformation']['message']}")
        elif event['type'] == "Microsoft.Communication.CallDisconnected":
            pass
     return Response(status=200)

# WebSocket.
@app.websocket('/ws')
async def ws():
    handler = OpenAIRTHandler()
    print("Client connected to WebSocket")
    await handler.init_incoming_websocket(websocket)
    await handler.start_client()
    try:
        while websocket:
            try:
                # Receive data from the client
                data = await websocket.receive()
                await handler.acs_to_oai(data)
                await handler.send_welcome()
            except Exception as e:
                print(f"WebSocket connection closed: {e}")
                break
    finally:
        await handler.ai_speech.stop_recognition()
        await handler.connection.close()
        await handler.incoming_websocket.close(code=1000, reason="Normal Closure")

# WebSocket for Transcription.
@app.websocket('/transcriptionws')
async def webSocketTranscription():
    handler = ACSTranscriptionHandler()
    print("Client connected to WebSocket Transcription")
    await handler.init_transcription_websocket(websocket)
    try:
        while True:
            try:
                # Receive data from the client
                data = await websocket.receive()
                await handler.handle_transcription(data)
            except Exception as e:
                print(f"Transcription WebSocket connection closed: {e}")
                break
    finally:
        await handler.transcription_websocket.close(code=1000, reason="Normal Closure")

@app.route('/')
def home():
    return 'Hello ACS CallAutomation!'

if __name__ == '__main__':
    app.logger.setLevel(INFO)
    app.run(port=8000)
