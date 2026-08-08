export const getInitials = (name) => {
  const parts = (name || '').trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return (name || 'U').slice(0, 2).toUpperCase();
};

export const getAvatarColor = (name) => {
  let hash = 0;
  const str = name || '';
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 60%, 35%)`;
};
