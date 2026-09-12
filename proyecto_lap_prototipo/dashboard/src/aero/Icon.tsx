export default function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, string> = {
    plane: 'M22 2 9 9 2 7 1 9 7 13 9 19 11 20 12 14 19 9Z M8 14 4 18',
    grid: 'M3 3H9V9H3Z M15 3H21V9H15Z M3 15H9V21H3Z M15 15H21V21H15Z',
    map: 'M3 5 9 3 15 5 21 3V19L15 21 9 19 3 21Z M9 3V19 M15 5V21',
    camera: 'M3 6H16V18H3Z M16 10 22 7V17L16 14Z',
    settings: 'M9 3H15L16 6 19 7 21 10 19 13 20 16 17 19 14 19 12 22 9 19 6 19 3 16 4 13 2 10 5 7 8 6Z M15 12A3 3 0 1 1 9 12 3 3 0 0 1 15 12',
    lab: 'M9 2H15 M10 2V9L4 19Q3 22 6 22H18Q21 22 20 19L14 9V2 M7 15H17',
    chart: 'M3 3V21H22 M7 16V12 M12 16V8 M17 16V4',
    report: 'M5 2H15L20 7V22H5Z M15 2V7H20 M8 12H17 M8 16H17',
    people: 'M14 6A3 3 0 1 1 8 6 3 3 0 0 1 14 6 M5 21V17A6 6 0 0 1 12 11 6 6 0 0 1 18 17V21 M18 4A3 3 0 0 1 18 10 M21 14V20',
    clock: 'M22 12A10 10 0 1 1 2 12 10 10 0 0 1 22 12 M12 6V12L16 15',
    shield: 'M12 2 21 6V12Q21 19 12 23 3 19 3 12V6Z M8 12 11 15 16 9',
    alert: 'M12 2 23 21H1Z M12 8V14 M12 18V18.2',
    upload: 'M12 16V2 M7 7 12 2 17 7 M3 15V22H21V15',
    download: 'M12 2V16 M7 11 12 16 17 11 M3 17V22H21V17',
    plus: 'M12 4V20 M4 12H20',
    check: 'M4 12 9 17 20 6',
    arrow: 'M3 12H21 M15 6 21 12 15 18',
    expand: 'M8 3H3V8 M16 3H21V8 M3 16V21H8 M16 21H21V16',
    eye: 'M1 12Q12 -2 23 12 12 26 1 12 M16 12A4 4 0 1 1 8 12 4 4 0 0 1 16 12',
    layers: 'M2 7 12 2 22 7 12 12Z M2 12 12 17 22 12 M2 17 12 22 22 17',
    pin: 'M19 9Q19 16 12 23 5 16 5 9A7 7 0 0 1 19 9 M14 9A2 2 0 1 1 10 9 2 2 0 0 1 14 9',
    user: 'M16 6A4 4 0 1 1 8 6 4 4 0 0 1 16 6 M3 22V18A9 9 0 0 1 21 18V22Z',
    link: 'M9 15 15 9 M7 14 4 17A4 4 0 0 0 10 22L14 18 M10 6 14 2A4 4 0 0 1 20 8L17 11',
    trash: 'M3 5H21 M9 5V2H15V5 M5 5 6 22H18L19 5 M10 9V18 M14 9V18',
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.grid}/></svg>;
}
