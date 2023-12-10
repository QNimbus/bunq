const script = (() => {
    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById("detailModal");
        const modalText = document.getElementById("modal-text");
        const rootStyle = getComputedStyle(document.documentElement);
        const transitionDuration = rootStyle.getPropertyValue('--modal-transition-duration');
        const durationInMs = parseFloat(transitionDuration) * 1000; // Convert the duration from seconds to milliseconds for setTimeout

        function isValidBase64(str) {
            const base64Regex = /^(?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)?$/;
            return base64Regex.test(str);
        }

        function decodeBase64() {
            document.querySelectorAll('span.encodedData').forEach(elem => {
                if (elem.children.length === 0 && isValidBase64(elem.textContent)) {
                    elem.textContent = atob(elem.textContent).slice(0, 100);
                    elem.classList.add('ellipsis');
                }
            });
        }

        function toggleDetailRow(clickedRow) {
            const detailRow = clickedRow.nextElementSibling;
            if (detailRow && detailRow.classList.contains('detail-row')) {
                detailRow.classList.toggle('visible');
                document.querySelectorAll('.detail-row.visible').forEach(row => {
                    if (row !== detailRow) row.classList.remove('visible');
                });
            }
        }

        function showModal(event) {
            const clickedElement = event.target;
            const modalTitle = clickedElement.getAttribute('data-modal-title');
            const decodedData = JSON.parse(atob(clickedElement.getAttribute('data-modal-content')));
            let content = `<strong>${modalTitle}:</strong><br>`;

            Object.entries(decodedData).forEach(([key, value]) => {
                let displayData = (typeof value === 'object') ? JSON.stringify(value, null, 2)
                    .replace(/^( +)/gm, match => match.replace(/ /g, '&nbsp;'))
                    .replace(/\n/g, '<br>') : value;
                content += `${key}: ${displayData}<br>`;
            });

            modalText.innerHTML = content;
            modal.style.display = "block";
            setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 0); // Wait for the next tick to add the class
        }

        function closeModal() {
            modal.querySelector('.modal-content').classList.remove('show');
            setTimeout(() => modal.style.display = "none", durationInMs);
        }

        document.addEventListener('click', (event) => {
            const clickedElement = event.target;
            const mainRow = clickedElement.closest('.main-row');

            if (clickedElement.hasAttribute('data-modal-title')) {
                showModal(event);
            } else if (clickedElement.classList.contains('close') || clickedElement === modal) {
                closeModal();
            } else if (mainRow && mainRow.tagName === 'TR') {
                toggleDetailRow(mainRow);
            }
        });

        document.querySelectorAll('tr.main-row, tr.detail-row').forEach(row => {
            row.addEventListener('mouseover', function () {
                const previousSibling = row.previousElementSibling;
                const nextSibling = row.nextElementSibling;

                if (row.classList.contains('main-row') && nextSibling?.classList.contains('detail-row')) {
                    row.classList.add('highlight');
                    nextSibling.classList.add('highlight');
                } else if (row.classList.contains('detail-row') && previousSibling?.classList.contains('main-row')) {
                    row.classList.add('highlight');
                    previousSibling.classList.add('highlight');
                }
            });

            row.addEventListener('mouseout', function () {
                const previousSibling = row.previousElementSibling;
                const nextSibling = row.nextElementSibling;

                if (row.classList.contains('main-row') && nextSibling?.classList.contains('detail-row')) {
                    row.classList.remove('highlight');
                    nextSibling.classList.remove('highlight');
                } else if (row.classList.contains('detail-row') && previousSibling?.classList.contains('main-row')) {
                    row.classList.remove('highlight');
                    previousSibling.classList.remove('highlight');
                }
            });
        });

        window.addEventListener('click', (event) => {
            if (event.target === modal) closeModal();
        });

        decodeBase64();
    });
})();
