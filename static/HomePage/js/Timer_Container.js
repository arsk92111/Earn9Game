
// Quantum Timer System
function quantumTimer() {
    const timer = document.getElementById('timer');
    let time = 86399;

    setInterval(() => {
        time--;
        const hours = Math.floor(time / 3600);
        const minutes = Math.floor((time % 3600) / 60);
        const seconds = time % 60;

        timer.innerHTML = `
    <span class="time-segment">${String(hours).padStart(2, '0')}</span>:
    <span class="time-segment">${String(minutes).padStart(2, '0')}</span>:
    <span class="time-segment">${String(seconds).padStart(2, '0')}</span>
    `;
    }, 1000);
}
quantumTimer();


function updateTimer() {
    const timer = document.getElementById('timer');
    let time = 86399; // 23:59:59 in seconds
    setInterval(() => {
        time--;
        const hours = Math.floor(time / 3600);
        const minutes = Math.floor((time % 3600) / 60);
        const seconds = time % 60;
        timer.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }, 1000);
}
updateTimer();

