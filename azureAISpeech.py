import azure.cognitiveservices.speech as speechsdk

# Cognitive Services Endpoint and key
COGNITIVE_SERVICES_ENDPOINT = "COGNITIVE_SERVICES_ENDPOINT"
COGNITIVE_SERVICES_KEY = "COGNITIVE_SERVICES_KEY"

class AISpeech:
    def __init__(
        self,
    ):
        speech_config = speechsdk.SpeechConfig(
            subscription=COGNITIVE_SERVICES_KEY,
            endpoint=COGNITIVE_SERVICES_ENDPOINT,
        )

        speech_config.set_property(
            speechsdk.PropertyId.Speech_SegmentationStrategy, "Semantic"
        )

        speech_config.speech_recognition_language = "ja-JP"

        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceResponse_RequestDetailedResultTrueFalse,
            "True",
        )

        audio_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000, bits_per_sample=16, channels=1
        )
        self.audio_stream = speechsdk.audio.PushAudioInputStream(
            stream_format=audio_format
        )
        audio_config = speechsdk.audio.AudioConfig(stream=self.audio_stream)

        self.speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        self.speech_recognizer.recognized.connect(self.recognized_callback)
        self.speech_recognizer.recognizing.connect(self.recognizing_callback)

        self.speech_recognizer.canceled.connect(self.canceled_callback)
    

    def recognizing_callback(self, evt: speechsdk.SpeechRecognitionEventArgs):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            # print(f"Recognizing: {evt.result.text}")
            pass
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized.")

    def recognized_callback(
            self, 
            evt: speechsdk.SpeechRecognitionEventArgs,
    ):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print(f" AI (ai speech):-- {evt.result.text}")
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized.")

    def canceled_callback(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        if evt.result.reason == speechsdk.CancellationReason.Error:
            print(f"Speech Recognition canceled: {evt.cancellation_details}")

    async def start_recognition(self) -> speechsdk.ResultFuture:
        print(f"start audio recognition.")
        return self.speech_recognizer.start_continuous_recognition_async()

    async def stop_recognition(self) -> speechsdk.ResultFuture:
        print(f"stop audio recognition.")
        return self.speech_recognizer.stop_continuous_recognition_async()

    async def send_audio_str(self, audio_data: str):
        import base64

        audio_bytes = base64.b64decode(audio_data)
        await self.send_audio_bytes(audio_bytes)

    async def send_audio_bytes(self, audio_bytes: bytes):
        self.audio_stream.write(audio_bytes)
