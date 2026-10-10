export function imageRect(imageWidth,imageHeight,canvasWidth,canvasHeight) {
    const scale=Math.min(canvasWidth/imageWidth,canvasHeight/imageHeight);
    const w=imageWidth*scale,h=imageHeight*scale;
    return {x:(canvasWidth-w)/2,y:(canvasHeight-h)/2,w,h};
}

export function normalizedPoint(clientX,clientY,box,rect,canvasWidth,canvasHeight) {
    if(!rect||!box.width||!box.height)return null;
    const scale=Math.min(box.width/canvasWidth,box.height/canvasHeight);
    const offsetX=(box.width-canvasWidth*scale)/2;
    const offsetY=(box.height-canvasHeight*scale)/2;
    const x=((clientX-box.left-offsetX)/scale-rect.x)/rect.w;
    const y=((clientY-box.top-offsetY)/scale-rect.y)/rect.h;
    return x<0||x>1||y<0||y>1?null:{x,y};
}
