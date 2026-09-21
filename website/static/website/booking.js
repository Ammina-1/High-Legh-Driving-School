const lessonSelect = document.getElementById('booking-lesson');
const dateButtons = document.querySelectorAll('.date-button');
const timeOptions = document.querySelectorAll('.time-option');
const slotInputs = document.querySelectorAll('input[name="slot"]');
const chooseDateMessage = document.getElementById('choose-date-message');
const summaryLesson = document.getElementById('summary-lesson');
const summaryPrice = document.getElementById('summary-price');
const summaryDate = document.getElementById('summary-date');
const summaryTime = document.getElementById('summary-time');
const submitButton = lessonSelect.form.querySelector('button[type="submit"]');
const dateFormatter = new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
});
let selectedDate = '';
let submitting = false;
const form = lessonSelect.form;
const buttonLabel = submitButton.textContent;

function updateSummary() {
    if (!summaryLesson) { submitButton.disabled = true; return; }
    const option = lessonSelect.selectedOptions[0];
    summaryLesson.textContent = option.dataset.lesson;
    summaryPrice.textContent = option.dataset.price;
    const selectedSlot = Array.from(slotInputs).find(input => input.checked && !input.disabled);
    summaryTime.textContent = selectedSlot ? selectedSlot.dataset.time : 'Select a time';
    summaryDate.textContent = selectedDate
        ? dateFormatter.format(new Date(`${selectedDate}T00:00:00Z`))
        : 'Select a date';
    submitButton.disabled = submitting || !selectedSlot;
}

function selectDate(date, resetTime = true) {
    selectedDate = date;
    dateButtons.forEach(button => {
        button.setAttribute('aria-pressed', String(button.dataset.date === date));
    });
    timeOptions.forEach(option => {
        const visible = option.dataset.date === date;
        const radio = option.querySelector('input[type="radio"]');
        option.classList.toggle('hidden', !visible);
        radio.disabled = !visible;
        if (resetTime || !visible) radio.checked = false;
    });
    if (chooseDateMessage) chooseDateMessage.classList.toggle('hidden', Boolean(date));
    updateSummary();
}

dateButtons.forEach(button => {
    button.addEventListener('click', () => selectDate(button.dataset.date, selectedDate !== button.dataset.date));
});
lessonSelect.addEventListener('change', updateSummary);
slotInputs.forEach(input => input.addEventListener('change', updateSummary));

function restoreSelection() {
    submitting = false;
    form.removeAttribute('aria-busy');
    submitButton.textContent = buttonLabel;
    document.getElementById('booking-status').textContent = '';
    const checkedSlot = Array.from(slotInputs).find(input => input.checked);
    selectDate(checkedSlot ? checkedSlot.dataset.date : selectedDate, false);
}
window.addEventListener('pageshow', restoreSelection);
restoreSelection();

form.addEventListener('submit', event => {
    if (submitting) { event.preventDefault(); return; }
    if (!Array.from(slotInputs).some(input => input.checked && !input.disabled)) {
        event.preventDefault();
        dateButtons[0]?.focus();
        return;
    }
    submitting = true;
    form.setAttribute('aria-busy', 'true');
    submitButton.disabled = true;
    submitButton.textContent = 'Booking…';
    document.getElementById('booking-status').textContent = 'Booking your lesson. Please wait.';
});
document.getElementById('booking-errors')?.focus();
