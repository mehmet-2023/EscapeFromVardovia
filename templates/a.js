if (!res.ok) {
    let errorMsg = data.error || data.detail || data.message || 'An unknown error occurred';
    
    if (typeof errorMsg === 'string') {
      if (errorMsg.includes('ERROR_JSON:')) {
        errorMsg = errorMsg.split('ERROR_JSON:')[1]?.trim() || errorMsg;
      }
      errorMsg = errorMsg
        .replace(/^"|"$/g, '')  
        .replace(/^\[|\]$/g, '') 
        .trim();
        
      if (errorMsg.length > 100) {
        const sentenceEnd = errorMsg.match(/[.!?]/);
        if (sentenceEnd) {
          errorMsg = errorMsg.substring(0, sentenceEnd.index + 1);
        } else {
          errorMsg = errorMsg.substring(0, 100) + '...';
        }
      }
    }
    
    await translateAndAddMessage(errorMsg, false);
  } else {
    if (data.narration) {
      await translateAndAddMessage(data.narration, false);
    }
    if (data.state) {
      updateStatus(data.state);
    }
    updateImage(data.image_url || '');
  }
} catch (err) {
  let errorMsg = err.message || 'An unknown error occurred';
  
  try {
    const errorObj = JSON.parse(errorMsg);
    errorMsg = errorObj.error || errorObj.detail || errorObj.message || errorMsg;
  } catch (e) {
    const errorParts = errorMsg.split(':').map(part => part.trim());
    errorMsg = errorParts.length > 1 ? errorParts.slice(1).join(': ') : errorMsg;
  }
  
  errorMsg = errorMsg
    .replace(/^"|"$/g, '')
    .replace(/^\[|\]$/g, '')
    .trim();
  
  await translateAndAddMessage(errorMsg, false);
} finally {
  hideLoading();
}
}