document.addEventListener('DOMContentLoaded', function () {
    let bookingId = window.bookingId;
    let stream = null;
    let idFile = null;
    let selfieFrames = [];
    let pollingInterval = null;

    window.validateIdSelection = function () {
        const idType = document.getElementById('id_type').value;
        const idNumber = document.getElementById('id_number').value.trim();
        const uploadZone = document.getElementById('upload-zone');

        if (idType && idNumber.length >= 5) {
            uploadZone.classList.remove('disabled');
        } else {
            uploadZone.classList.add('disabled');
        }
    };

    window.handleUploadClick = function () {
        if (document.getElementById('upload-zone').classList.contains('disabled')) {
            alert('Please select an ID type and enter the ID number first.');
            return;
        }
        document.getElementById('id_document').click();
    };

    window.handleIdUpload = function (input) {
        if (input.files && input.files[0]) {
            idFile = input.files[0];
            const reader = new FileReader();
            reader.onload = function (e) {
                document.getElementById('id-image').src = e.target.result;
                document.getElementById('upload-zone').style.display = 'none';
                document.querySelector('.kyc-controls-grid').style.display = 'none';
                document.getElementById('id-preview').style.display = 'block';
            };
            reader.readAsDataURL(idFile);
        }
    };

    window.resetIdUpload = function () {
        idFile = null;
        document.getElementById('id-preview').style.display = 'none';
        document.getElementById('upload-zone').style.display = 'block';
        document.querySelector('.kyc-controls-grid').style.display = 'grid';
        document.getElementById('id_document').value = '';
    };

    window.proceedToCamera = async function () {
        const idType = document.getElementById('id_type').value;
        const idNumber = document.getElementById('id_number').value.trim();

        const btn = document.getElementById('btn-proceed-camera');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating...';

        const formData = new FormData();
        formData.append('id_type', idType);
        formData.append('id_number', idNumber);
        formData.append('id_document', idFile);

        try {
            const res = await fetch(`/api/bookings/${bookingId}/upload-id`, { method: 'POST', body: formData });
            if (res.ok) {
                document.getElementById('step-id-upload').style.display = 'none';
                document.getElementById('scanner-container').style.display = 'block';
            } else {
                const data = await res.json();
                alert('Error: ' + (data.detail || 'Failed to validate ID Pattern'));
                btn.disabled = false;
                btn.innerHTML = 'Use this ID <i class="fas fa-arrow-right"></i>';
            }
        } catch (err) {
            alert('Network error. Check connection.');
            btn.disabled = false;
            btn.innerHTML = 'Use this ID <i class="fas fa-arrow-right"></i>';
        }
    };

    window.startRealtimeScanner = async function () {
        const video = document.getElementById('webcam');
        const constraints = [
            { video: { facingMode: "user" } },
            { video: true }
        ];

        let success = false;
        for (const config of constraints) {
            try {
                logger_kyc("Attempting camera with config: " + JSON.stringify(config));
                stream = await navigator.mediaDevices.getUserMedia(config);
                success = true;
                break;
            } catch (err) {
                console.warn("Camera attempt failed", config, err);
            }
        }

        if (success) {
            video.srcObject = stream;
            document.getElementById('btn-start-scan').style.display = 'none';
            document.getElementById('liveliness-prompt').style.display = 'block';
            document.getElementById('capture-progress').style.display = 'block';
            document.getElementById('scan-line').style.display = 'block';

            // Sequential capture logic
            const prompts = [
                "Stay still...",
                "Blink your eyes!",
                "Turn your head slightly..."
            ];

            for (let i = 0; i < 3; i++) {
                document.getElementById('prompt-instruction').innerText = prompts[i];
                document.getElementById('scan-feedback').innerText = `Capturing Frame ${i + 1}/3...`;
                await new Promise(r => setTimeout(r, 1200));
                captureFrame(i + 1);
                document.getElementById(`dot-${i + 1}`).classList.add('active');
            }

            finalizeCapture();
        } else {
            alert("Hindi ma-access ang camera. Pakisiguraduhin na naka-allow ang camera permissions sa iyong browser.");
        }
    };

    function logger_kyc(msg) {
        console.log("[KYC Debug]", msg);
    }

    function captureFrame(index) {
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('frame-canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);

        canvas.toBlob((blob) => {
            selfieFrames.push(new File([blob], `selfie_${index}.jpg`, { type: 'image/jpeg' }));
        }, 'image/jpeg', 0.9);
    }

    async function finalizeCapture() {
        document.getElementById('scan-line').style.display = 'none';
        document.getElementById('scan-feedback').innerText = "Capture Complete";

        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }

        document.getElementById('scanner-container').style.display = 'none';
        document.getElementById('step-processing').style.display = 'block';

        const formData = new FormData();
        selfieFrames.forEach(file => formData.append('selfies', file));

        try {
            const res = await fetch(`/api/bookings/${bookingId}/verify-full`, { method: 'POST', body: formData });
            const data = await res.json();

            if (res.ok) {
                updateStatus("Background Processing Started", "Our AI is analyzing your biometrics. Please do not close this window.");
                startPolling();
            } else {
                handleRejection(data.detail);
            }
        } catch (err) {
            handleRejection("Connection lost during upload.");
        }
    }

    function startPolling() {
        pollingInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/bookings/${bookingId}/status`);
                const data = await res.json();

                if (data.status === 'processing') {
                    updateStatus("Verification in Progress...", "Analyzing patterns and fraud signals...");
                } else if (data.status === 'approved') {
                    stopPolling();
                    handleApproval(data);
                } else if (data.status === 'rejected' || data.status === 'blocked') {
                    stopPolling();
                    handleRejection(data.reason || "Verification failed.");
                } else if (data.status === 'manual_review') {
                    stopPolling();
                    handleManualReview();
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 3000);
    }

    function stopPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
    }

    function handleApproval(data) {
        document.getElementById('processing-spinner').style.display = 'none';
        document.getElementById('fraud-meter').style.display = 'block';
        document.getElementById('fraud-bar').style.width = data.fraud_score + "%";

        updateStatus("Verification Approved!", "Trust Score: " + data.fraud_score + "/100");
        document.getElementById('status-text').style.color = "var(--primary-color)";

        setTimeout(() => {
            document.getElementById('btn-next').style.display = 'inline-block';
            window.location.href = `/bookings/step/quotation/${bookingId}`;
        }, 2000);
    }

    function handleManualReview() {
        document.getElementById('processing-spinner').style.display = 'none';
        updateStatus("Pending Manual Review", "Your data requires a second look by our compliance team. We will notify you shortly.");
        document.getElementById('status-text').style.color = "#f59e0b";

        setTimeout(() => {
            window.location.href = "/customer/dashboard";
        }, 3000);
    }

    function updateStatus(title, sub) {
        document.getElementById('status-text').innerText = title;
        document.getElementById('status-subtext').innerText = sub;
    }

    function handleRejection(msg) {
        document.getElementById('processing-spinner').style.display = 'none';
        document.getElementById('retry-container').style.display = 'block';
        updateStatus("Security Rejection", msg);
        document.getElementById('status-text').style.color = "#dc2626";
    }
});
