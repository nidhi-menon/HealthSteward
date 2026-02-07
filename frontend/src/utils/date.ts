/**
 * Format a date string (YYYY-MM-DD) for display without timezone conversion.
 * Use this for dates like DOB, diagnosed date, etc. that shouldn't shift.
 */
export function formatDateString(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';

  // Parse the date parts directly from the string to avoid timezone issues
  const [year, month, day] = dateStr.split('T')[0].split('-');

  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];

  const monthIndex = parseInt(month, 10) - 1;
  const dayNum = parseInt(day, 10);

  return `${months[monthIndex]} ${dayNum}, ${year}`;
}

/**
 * Format a date string as Month Year only (for diagnosed dates).
 */
export function formatMonthYear(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';

  const [year, month] = dateStr.split('T')[0].split('-');

  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const monthIndex = parseInt(month, 10) - 1;

  return `${months[monthIndex]} ${year}`;
}

/**
 * Format a datetime string for display WITH timezone conversion.
 * Use this for appointments and other time-sensitive dates.
 */
export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString();
}

/**
 * Format a datetime string as just the date part WITH timezone conversion.
 * Use this for appointment dates when you only want to show the date.
 */
export function formatDateWithTimezone(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString();
}
