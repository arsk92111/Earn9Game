document.addEventListener('DOMContentLoaded', function() {
    particlesJS('particles', {
        particles: {
            number: { value: 80 },
            color: { value: '#3b82f6' },
            opacity: { value: 0.5 },
            size: { value: 3 },
            move: { 
                enable: true,
                speed: 1,
                direction: 'bottom',
                out_mode: 'out'
            }
        }
    });
}); 
      


let selectedSide = null;
let balance = 1000;
let currentBid = 0;
let countdownInterval = null;

const socket = new WebSocket(
        (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + 
    window.location.host + '/ws/card_game/live_card_game'
    );

    // WebSocket Handlers
    socket.onmessage = async (e) => {
        try {
            const data = JSON.parse(e.data);
            switch(data.type) {
                case 'timer.update':
                    handleTimer(data);
                    break;
                case 'bids.update':
                    updateBids(data.bids);
                    break;
                case 'results.show':
                    showResults(data);
                    break;
                case 'balance.update':
                    updateBalance(data.coins);
                    break;
                case 'round_start':
                    handleRoundStart(data);
                    break;
            }
        } catch (error) {
            showError('Connection error - please refresh!');
        }
    };

    
      function handleRoundStart(data) {
          // Clear existing timer
          if(countdownInterval) clearInterval(countdownInterval);
          
          // Reset UI state
          currentBid = 0;
          selectedSide = null;
          document.getElementById('current-bid').textContent = '0';
          document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
          
          // Update card display with proper value detection
          const [value, _, suit] = data.card.split(' ');
          const isPicture = ['JACK', 'QUEEN', 'KING', 'ACE'].includes(value.toUpperCase());
          
          // Set card content
          document.getElementById('number-card-back').textContent = isPicture ? 'PICTURE' : 'NUMBER';
          document.getElementById('picture-card-back').textContent = isPicture ? 'PICTURE' : 'NUMBER';
          
          // Update card images
          const cardImage = `/static/cards/${value.toLowerCase()}_of_${suit.toLowerCase()}.png`;
          document.getElementById('number-card-img').src = cardImage;
          document.getElementById('picture-card-img').src = cardImage;
          // Reset bet displays
          totalNumberBets = 0;
          totalPictureBets = 0;
          document.querySelectorAll('.total-bet-amount, .current-user-bet').forEach(el => el.textContent = '0');
          // Play flip sound
          document.getElementById('flipSound').play();

      }
      

        let totalNumberBets = 0;
        let totalPictureBets = 0;
        function handleTimer(data) {
            if (countdownInterval) clearInterval(countdownInterval);

            const serverStartTime = new Date(data.start_time).getTime();
            const timerElement = document.getElementById('timer');

            countdownInterval = setInterval(() => {
                const now = Date.now();
                const elapsed = Math.floor((now - serverStartTime) / 1000);
                const seconds = Math.max(0, 30 - elapsed);

                timerElement.textContent = seconds;
                timerElement.classList.toggle('timer-pulse', seconds <= 10);

                if (seconds <= 5) {
                    document.getElementById('tickSound').play().catch(() => {});
                }

                if (seconds === 0) {
                    clearInterval(countdownInterval);
                }
            }, 1000);

            // Enable or disable betting based on phase
            if (data.phase === 'bidding') {
                enableBetting();
            } else {
                disableBetting();
            }
        }


        function updateBids(bids) {
            const bidsList = document.getElementById('players-list');
            bidsList.innerHTML = bids.map(bid => `
                <div class="flex justify-between items-center bg-gray-700 p-3 rounded-lg mb-2">
                    <span>${bid.player__user__username} ${bid.player__user__db_phone_number}</span>
                    <div class="flex items-center gap-2">
                        <span class="text-blue-400">${bid.amount}</span>
                        <span class="text-sm ${bid.side === 'number' ? 'bg-blue-600' : 'bg-red-600'} px-2 py-1 rounded">
                            ${bid.side.toUpperCase()}
                        </span>
                    </div>
                </div>
            `).join('');

            // Update total bets
              totalNumberBets = bids.filter(b => b.side === 'number').reduce((a,b) => a + b.amount, 0);
              totalPictureBets = bids.filter(b => b.side === 'picture').reduce((a,b) => a + b.amount, 0);
              
              document.querySelector('#number-card .total-bet-amount').textContent = totalNumberBets;
              document.querySelector('#picture-card .total-bet-amount').textContent = totalPictureBets;
        }

  
        function showResults(data) {
            const modal = document.getElementById('results-modal');
            const winnerDisplay = document.getElementById('winning-card-display');
            
            // Update winner display
            winnerDisplay.textContent = `${data.winning_side.toUpperCase()} WINS! (${data.card})`;
            document.getElementById(`${data.winning_side}-card`).classList.add('winner-glow');
            
            // Update results table
            const resultsBody = document.getElementById('summary-body');
            resultsBody.innerHTML = data.results.map(result => `
                <tr class="hover:bg-gray-700">
                    <td class="p-3">${result.username}</td>
                    <td class="p-3">${result.bid}</td>
                    <td class="p-3">${result.share}</td>
                    <td class="p-3 text-red-400">-${result.fee}</td>
                    <td class="p-3 font-bold text-green-400">+${result.final_win}</td>
                </tr>
            `).join('');
            
            totalNumberBets = 0;
            totalPictureBets = 0;
            
              document.querySelector('#number-card .total-bet-amount').textContent = totalNumberBets;
              document.querySelector('#picture-card .total-bet-amount').textContent = totalPictureBets;
            // Show modal
            modal.classList.remove('hidden');
            setTimeout(() => {
                modal.classList.add('hidden');
                document.getElementById(`${data.winning_side}-card`).classList.remove('winner-glow');
            }, 3000);

             // Add confetti particles
        for(let i = 0; i < 20; i++) {
            createParticle(document.getElementById(`${data.winning_side}-card`));
        }
        }

        // UI Interaction Functions
        function selectSide(side) {
            selectedSide = side;
            document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
            document.getElementById(`${side}-card`).classList.add('selected');
        }

     
    function createParticle(element) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.cssText = `
            position: absolute;
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            font-size: ${Math.random() * 20 + 10}px;
            animation: particle ${Math.random() * 1 + 0.5}s ease-out;
        `;
        particle.textContent = ['🎉', '✨', '🌟'][Math.floor(Math.random() * 3)];
        element.appendChild(particle);
        
        setTimeout(() => particle.remove(), 1500);
    }

    // Add 3D card tilt effect
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.transform = `
                perspective(1000px)
                rotateX(${(y - rect.height/2) / 10}deg)
                rotateY(${-(x - rect.width/2) / 10}deg)
            `;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
        });
    });

        document.querySelectorAll('.coin-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const amount = parseInt(btn.dataset.amount);
                if (currentBid + amount > balance) {
                    showError('Insufficient balance!');
                    return;
                }
                currentBid += amount;
                updateCurrentBidDisplay();
            });
        }); 


        function confirmBet() {
            if (!selectedSide || currentBid === 0) {
                showError('Please select a side and amount!');
                return;
            }
            
            if (currentBid > balance) {
                showError('Exceeds balance!');
                return;
            }

            socket.send(JSON.stringify({
                type: 'place_bid',
                amount: currentBid,
                side: selectedSide
            }));

            // Visual feedback
            const confirmBtn = document.getElementById('confirm-bet-btn');
            confirmBtn.classList.add('animate-pulse');
            setTimeout(() => confirmBtn.classList.remove('animate-pulse'), 200);

             if(selectedSide === 'number') {
                totalNumberBets += currentBid;
                document.querySelector('#number-card .total-bet-amount').textContent = totalNumberBets;
            } else {
                totalPictureBets += currentBid;
                document.querySelector('#picture-card .total-bet-amount').textContent = totalPictureBets;
            }
            
            // Update current user bet display
            document.querySelectorAll(`.${selectedSide}-card .current-user-bet`).textContent = currentBid;
        }

        function updateBalance(coins) {
            balance = coins;
            document.getElementById('player-balance').textContent = coins;
        }

        function enableBetting() {
            document.querySelectorAll('.coin-btn, #confirm-bet-btn').forEach(btn => btn.disabled = false);
            document.querySelectorAll('.card').forEach(c => c.style.pointerEvents = 'auto');
        }

        function disableBetting() {
            document.querySelectorAll('.coin-btn, #confirm-bet-btn').forEach(btn => btn.disabled = true);
            document.querySelectorAll('.card').forEach(c => c.style.pointerEvents = 'none');
        }

        function showError(message) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'fixed top-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg animate-fade-in';
            errorDiv.textContent = message;
            
            document.body.appendChild(errorDiv);
            setTimeout(() => errorDiv.remove(), 3000);
        }

        function updateCurrentBidDisplay() {
            document.getElementById('current-bid').textContent = currentBid;
        }
 
        document.addEventListener('DOMContentLoaded', () => {
            disableBetting();
        });
 
