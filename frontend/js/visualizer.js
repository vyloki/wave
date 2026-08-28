/**
 * Wave — Audio Visualizer
 * Canvas-based frequency visualization using Web Audio API.
 * Renders smooth floating bars and a glowing wave reacting to the audio.
 */

const Visualizer = {
    canvas: null,
    ctx: null,
    audioContext: null,
    analyser: null,
    sourceNode: null,
    dataArray: null,
    isActive: false,
    animationId: null,
    connected: false,

    barCount: 48,
    barGap: 3,
    smoothing: 0.82,

    init() {
        this.canvas = document.getElementById('visualizer-canvas');
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();

        window.addEventListener('resize', () => this.resizeCanvas());
    },

    resizeCanvas() {
        if (!this.canvas) return;
        this.canvas.width = this.canvas.offsetWidth * window.devicePixelRatio;
        this.canvas.height = this.canvas.offsetHeight * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    },

    connectToPlayer() {
        if (this.connected || !Player?.audio) return;

        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = this.smoothing;

            this.sourceNode = this.audioContext.createMediaElementSource(Player.audio);
            this.sourceNode.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.connected = true;
            this.start();
        } catch (error) {
            console.debug('Visualizer audio context init:', error);
        }
    },

    start() {
        if (this.isActive) return;
        this.isActive = true;
        this.animate();
    },

    stop() {
        this.isActive = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    },

    animate() {
        if (!this.isActive) return;
        this.animationId = requestAnimationFrame(() => this.animate());
        this.draw();
    },

    draw() {
        if (!this.ctx || !this.canvas || !this.analyser) return;

        const width = this.canvas.offsetWidth;
        const height = this.canvas.offsetHeight;

        this.ctx.clearRect(0, 0, width, height);
        this.analyser.getByteFrequencyData(this.dataArray);

        const totalBarWidth = (width - (this.barCount - 1) * this.barGap) / this.barCount;
        const barWidth = Math.max(3, totalBarWidth);

        for (let i = 0; i < this.barCount; i++) {
            const dataIndex = Math.floor((i / this.barCount) * this.dataArray.length * 0.65);
            const value = this.dataArray[dataIndex] || 0;
            const barHeight = Math.max(3, (value / 255) * height * 0.85);

            const x = i * (barWidth + this.barGap);
            const y = height - barHeight;

            const gradient = this.ctx.createLinearGradient(x, height, x, y);
            gradient.addColorStop(0, 'rgba(196, 168, 130, 0.2)');
            gradient.addColorStop(0.5, 'rgba(196, 168, 130, 0.6)');
            gradient.addColorStop(1, 'rgba(168, 139, 101, 0.9)');

            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
            this.ctx.fill();
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    Visualizer.init();

    if (Player?.audio) {
        Player.audio.addEventListener('play', () => {
            if (!Visualizer.connected) {
                Visualizer.connectToPlayer();
            }
            if (Visualizer.audioContext?.state === 'suspended') {
                Visualizer.audioContext.resume();
            }
        });
    }
});
