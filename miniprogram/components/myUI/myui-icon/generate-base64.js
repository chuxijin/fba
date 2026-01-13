const fs = require('fs');
const path = require('path');

const ttfPath = path.join(__dirname, 'myui-icon.ttf');
const data = fs.readFileSync(ttfPath);
const base64 = data.toString('base64');
const fontUrl = `data:font/truetype;charset=utf-8;base64,${base64}`;

console.log('Font base64 URL generated!');
console.log('Total base64 length:', base64.length);

// 生成 font-base64.js 文件
const output = `// Auto-generated - myui-icon font base64
export default '${fontUrl}';
`;

fs.writeFileSync(path.join(__dirname, 'myui-icon-base64.js'), output);
console.log('Generated: myui-icon-base64.js');
