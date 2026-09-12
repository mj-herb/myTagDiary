window.onload = function () {
  const canvas = document.getElementById("pixelCanvas");
  const ctx = canvas.getContext("2d");

  const img = new Image();
  img.src = "../static/images/hibiscus.jpeg";
  img.crossOrigin = "anonymous";

  img.onload = function () {
    // 축소된 크기 설정 (예: 20x20)
    const pixelWidth = 20;
    const pixelHeight = 20;

    // 임시 캔버스 (저해상도)
    const tempCanvas = document.createElement("canvas");
    const tempCtx = tempCanvas.getContext("2d");
    tempCanvas.width = pixelWidth;
    tempCanvas.height = pixelHeight;

    // 원본 이미지 축소해 임시 캔버스에 그림 (해상도 낮춤)
    tempCtx.drawImage(img, 0, 0, pixelWidth, pixelHeight);

    // 다시 원래 캔버스 크기로 확대
    canvas.width = pixelWidth * 10; // 픽셀 하나당 20px 크기로 확대
    canvas.height = pixelHeight * 10;

    // 확대할 때 이미지 스무딩 끄기 (픽셀화 효과)
    ctx.imageSmoothingEnabled = false;

    // 픽셀화된 이미지를 크게 그림
    ctx.drawImage(
      tempCanvas,
      0,
      0,
      tempCanvas.width,
      tempCanvas.height,
      0,
      0,
      canvas.width,
      canvas.height
    );
  };
};
