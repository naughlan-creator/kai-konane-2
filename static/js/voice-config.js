const voiceConfig = {
    lang: 'en-US',
    voiceName: 'Microsoft Zira Desktop',
    pitch: 1.1,
    rate: 0.7,
    volume: 1.0
  };
  
function initializeVoice() {
  return new Promise((resolve) => {
    const checkVoices = () => {
      const voices = speechSynthesis.getVoices();
      if (voices.length > 0) {
        const preferredVoices = [
          'Microsoft Zira',
          'Google US English Female',
          'Samantha',
          'Victoria'
        ];
          
        const selectedVoice = voices.find(voice => 
          preferredVoices.some(preferred => 
            voice.name.includes(preferred) && voice.lang.startsWith('en')
          )
        );
          
        if (selectedVoice) {
          voiceConfig.voice = selectedVoice;
        }
        resolve();
      } else {
        setTimeout(checkVoices, 10);
      }
    };
      
    checkVoices();
  });
}
  
const voiceSettings = {
  preferredVoices: [
      'Microsoft Zira Desktop',
      'Google US English Female',
      'Samantha',
      'Victoria'
  ],
  speechConfig: {
      rate: 0.8,
      pitch: 1.1,
      volume: 1.0,
      lang: 'en-US'
  }
};

function getBestVoice() {
  const voices = speechSynthesis.getVoices();
  return voices.find(voice => 
      voiceSettings.preferredVoices.includes(voice.name) || 
      (voice.name.includes('Female') && voice.lang.startsWith('en'))
  ) || voices.find(voice => voice.lang.startsWith('en')) || voices[0];
}
