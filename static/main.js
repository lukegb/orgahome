document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('user-grid');
    if (!grid) return; // Guard clause in case it's used on pages without grid

    // Store initial cards to restore from
    const initialCards = Array.from(document.querySelectorAll('.user-card'));

    const filterSelect = document.getElementById('team-filter');
    if (!filterSelect) return;

    filterSelect.addEventListener('change', function (e) {
        const selectedTeam = e.target.value;

        // Clear grid
        grid.innerHTML = '';

        if (selectedTeam === 'all') {
            // Restore all cards, sorted by name
            initialCards.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));
            initialCards.forEach(card => {
                card.style.display = 'block';
                grid.appendChild(card);
            });
            return;
        }

        // Filter and Section
        const leads = [];
        const members = [];

        initialCards.forEach(card => {
            const teams = JSON.parse(card.dataset.teams);
            const teamInfo = teams.find(t => t.name === selectedTeam);

            if (teamInfo) {
                card.style.display = 'block';
                if (teamInfo.is_lead) {
                    leads.push(card);
                } else {
                    members.push(card);
                }
            } else {
                card.style.display = 'none';
            }
        });

        // Sort each group
        leads.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));
        members.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));

        // Append with Headers
        if (leads.length > 0) {
            const header = document.createElement('h2');
            header.className = 'grid-header';
            header.textContent = 'Team Leads';
            grid.appendChild(header);
            leads.forEach(card => grid.appendChild(card));
        }

        if (members.length > 0) {
            const header = document.createElement('h2');
            header.className = 'grid-header';
            header.textContent = 'Team Members';
            grid.appendChild(header);
            members.forEach(card => grid.appendChild(card));
        }

        if (leads.length === 0 && members.length === 0) {
            const msg = document.createElement('div');
            msg.textContent = 'No active members found in this team.';
            msg.className = 'empty-message';
            grid.appendChild(msg);
        }
    });
});

/* Mobile Menu Toggle */
document.addEventListener('DOMContentLoaded', () => {
    const hamburger = document.getElementById('hamburger-menu');
    const navLinks = document.getElementById('nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', (e) => {
            e.stopPropagation();
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (navLinks.classList.contains('active') && !navLinks.contains(e.target)) {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            }
        });

        // Close menu when clicking a link
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
            });
        });
    }
});
