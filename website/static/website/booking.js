const lessonSelect = document.getElementById('booking-lesson');
const dateInput = document.getElementById('booking-date');
const timeButtons = document.querySelectorAll('[data-booking-time]');
const summaryLesson = document.getElementById('summary-lesson');
const summaryPrice = document.getElementById('summary-price');
const summaryDate = document.getElementById('summary-date');
const summaryTime = document.getElementById('summary-time');
const dateFormatter = new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
});

function updateSummary() {
    const option = lessonSelect.selectedOptions[0];
    summaryLesson.textContent = option.dataset.lesson;
    summaryPrice.textContent = option.dataset.price;
    summaryDate.textContent = dateInput.value
        ? dateFormatter.format(new Date(`${dateInput.value}T00:00:00Z`))
        : 'Select a date';
}

lessonSelect.addEventListener('change', updateSummary);
dateInput.addEventListener('input', updateSummary);
dateInput.addEventListener('change', updateSummary);

timeButtons.forEach(button => {
    button.addEventListener('click', () => {
        timeButtons.forEach(timeButton => {
            timeButton.setAttribute('aria-pressed', String(timeButton === button));
        });
        summaryTime.textContent = button.dataset.bookingTime;
    });
});

window.addEventListener('pageshow', updateSummary);
updateSummary();
