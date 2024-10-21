console.log('sounds.js loaded');
class AudioManager {
    constructor() {
        this.context = new (window.AudioContext || window.webkitAudioContext)();
        this.sounds = {};
        this.masterGainNode = this.context.createGain();
        this.masterGainNode.connect(this.context.destination);
        this.setVolume(this.getStoredVolume());
        console.log('AudioManager initialized');
    }

    initializeContext() {
        if (!this.context) {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            console.log('AudioContext initialized');
        }
    }

    loadSound(id, url) {
        console.log(`Loading sound: ${id} from ${url}`);
        return fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.arrayBuffer();
            })
            .then(arrayBuffer => this.context.decodeAudioData(arrayBuffer))
            .then(audioBuffer => {
                this.sounds[id] = audioBuffer;
                console.log(`Sound ${id} loaded successfully`);
            })
            .catch(e => console.error(`Error loading sound ${id}: ${e.message}`));
    }

    playSound(id) {
        console.log(`Attempting to play sound: ${id}`);
        if (this.sounds[id]) {
            const source = this.context.createBufferSource();
            source.buffer = this.sounds[id];
            source.connect(this.masterGainNode);
            source.start(0);
            console.log(`Playing sound: ${id}`);
            return new Promise(resolve => {
                source.onended = resolve;
            });
        } else {
            console.error(`Sound not found: ${id}`);
            return Promise.resolve();
        }
    }

    setVolume(volume) {
        this.masterGainNode.gain.setValueAtTime(volume, this.context.currentTime);
        localStorage.setItem('appVolume', volume);
    }

    getStoredVolume() {
        return parseFloat(localStorage.getItem('appVolume') || '1');
    }
}

const audioManager = new AudioManager();

// Existing sound functions
function playSound(soundId) {
    audioManager.initializeContext(); // Initialize context before playing
    return audioManager.playSound(soundId);
}

function playCorrectAnswer() {
    return playSound('correctAnswer');
}

function playIncorrectAnswer() {
    return playSound('incorrectAnswer');
}

function playActivityStart() {
    return playSound('activityStart');
}

function playActivityEnd() {
    return playSound('activityEnd');
}

function playActivityMusic() {
    return playSound('activityMusic');
}

function playNextQuestion() {
    return playSound('nextQuestion');
}

function playSwitchPage() {
    return playSound('switchPage');
}

function playOptionSelected() {
    return playSound('click');
}

function playStoryStart() {
    return playSound('storyStart');
}

function playStoryEnd() {
    return playSound('storyEnd');
}

function playUniversalSuccess() {
    return playSound('universalSuccess');
}

function playChildPage() {
    return playSound('childPage');
}

function playNext() {
    return playSound('next');
}

function playBack() {
    return playSound('back');
}

function playBye() {
    return playSound('bye');
}

function playError() {
    return playSound('error');
}

function playAdminPage() {
    return playSound('adminPage');
}

function playTeacherPage(){
    return playSound('teacherPage');
}

function playParentPage() {
    return playSound('parentPage');
}

function playLetterTyped(){
    return playSound('letter_typed');
}

function playLetterDeleted(){
    return playSound('letter_deleted');
}

function playPasswordTyped(){
    return playSound('password_typed');
}

function playAdminMusic(){
    return playSound('adminMusic');
}

function playChildMusic(){
    return playSound('childMusic');
}

function playParentMusic(){
    return playSound('parentMusic');
}

function playTeacherMusic(){
    return playSound('teacherMusic');
}

function playResults(){
    return playSound('results');
}

function playProgress(){
    return playSound('progress');
}

function playFeedback(){
    return playSound('feedback');
}

// New function for playing sound and then navigating
function playAndNavigate(soundId, url) {
    playSound(soundId).then(() => {
        window.location.href = url;
    });
}

function initializeVolumeControl() {
    const volumeSlider = document.getElementById('volumeSlider');
    if (volumeSlider) {
        volumeSlider.value = audioManager.getStoredVolume() * 100;
        volumeSlider.addEventListener('input', function() {
            const volume = this.value / 100;
            audioManager.setVolume(volume);
        });
    }
}

// Load sounds on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM content loaded, initializing sounds');
    initializeVolumeControl();
    const soundsToLoad = [
        { id: 'bye', url: '/static/sounds/bye.mp3' },
        { id: 'universalSuccess', url: '/static/sounds/universal_success.wav' },
        { id: 'click', url: '/static/sounds/click.wav' },
        { id: 'incorrectAnswer', url: '/static/sounds/incorrect.wav' },
        { id: 'correctAnswer', url: '/static/sounds/correct.wav' },
        { id: 'next', url: '/static/sounds/next.wav' },
        { id: 'back', url: '/static/sounds/back.wav' },
        { id: 'nextQuestion', url: '/static/sounds/next_question.wav' },
        { id: 'activityStart', url: '/static/sounds/activity_start.wav' },
        { id: 'activityEnd', url: '/static/sounds/activity_end.wav' },
        { id: 'activityMusic', url: '/static/sounds/activity_music.wav' },
        { id: 'storyStart', url: '/static/sounds/story_start.wav' },
        { id: 'storyEnd', url: '/static/sounds/story_end.wav' },
        { id: 'switchPage', url: '/static/sounds/switch_page.wav' },
        { id: 'error', url: '/static/sounds/error.wav' },
        { id: 'childPage', url: '/static/sounds/hello_child.wav' },
        { id: 'adminPage', url: '/static/sounds/hello_admin.wav' },
        { id: 'parentPage', url: '/static/sounds/hello_parent.wav' },
        { id: 'teacherPage', url: '/static/sounds/hello_teacher.wav' },
        { id: 'childMusic', url: '/static/sounds/child_music.wav' },
        { id: 'teacherMusic', url: '/static/sounds/teacher_music.wav' },
        { id: 'parentMusic', url: '/static/sounds/parent_music.wav' },
        { id: 'adminMusic', url: '/static/sounds/admin_music.wav' },
        { id: 'letter_typed', url: '/static/sounds/letter_typed.wav' },
        { id: 'letter_deleted', url: '/static/sounds/letter_deleted.wav' },
        { id: 'password_typed', url: '/static/sounds/password_letter_typed.mp3' },
        { id: 'results', url: '/static/sounds/results.wav' },
        { id: 'progress', url: '/static/sounds/progress.wav' },
        { id: 'feedback', url: '/static/sounds/feedback.wav' }
    ];

    Promise.all(soundsToLoad.map(sound => audioManager.loadSound(sound.id, sound.url)))
    .then(() => {
        console.log('All sounds loaded successfully');
        document.querySelectorAll('button').forEach(button => {
            button.disabled = false;
        });
        window.audioManager.soundsLoaded = true;
        document.dispatchEvent(new Event('soundsLoaded'));
    })
    .catch(error => console.error('Error loading sounds:', error));
    
    document.querySelectorAll('button').forEach(button => {
        button.disabled = true;
    });
});

window.audioManager = audioManager;