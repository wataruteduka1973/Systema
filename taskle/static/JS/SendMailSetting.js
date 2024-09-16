let decodedSelectedOption;
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('showsenddeta').addEventListener('submit', function(event){
        event.preventDefault();
        let selected_Option = document.getElementById("SendTemplate").value;
       
        try {
           decodedSelectedOption = decodeURIComponent(selected_Option);
           
        } catch(e) {
           console.error('Decoding failed', e);
           alert('テンプレートを正しく取得できませんでした');
        }
        fetch(`/taskle/update_fields/${encodeURIComponent(selected_Option)}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({selected_Option: decodedSelectedOption})
         })
         .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json(); 
        })
        
        .then(data => {
            document.getElementById("SendAdress").value = data.Adress;
            document.getElementById("SendMailText").value = data.Mailtext;
            const todayValue = data.Todays;
            const dt = new Date();

            let sendSubjectText = data.Subject;

            switch (todayValue) {
                case "option1":
                    sendSubjectText = `${(dt.getMonth() + 1)}月${dt.getDate()}日 (${dt.toLocaleDateString('ja-JP', { weekday: 'short' })})` + sendSubjectText;
                    break;
                case "option2":
                    sendSubjectText = `${(dt.getMonth() + 1)}月${dt.getDate()}日` + sendSubjectText;
                    break;
                case "option3":
                    sendSubjectText = dt.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', weekday: 'short' }) + sendSubjectText;
                    break;
                case "option4":
                    sendSubjectText = dt.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric' }) + sendSubjectText;
                    break;
                case "option5":
                    break;
                default:  
                    break;
            }

            document.getElementById("SendSubject").value = sendSubjectText;
        });
    });

    document.getElementById('showdeletedeta').addEventListener('submit', function(event){
        event.preventDefault();
        let selected_Option = document.getElementById("DeleteTemplate").value;
       
        try {
           decodedSelectedOption = decodeURIComponent(selected_Option);
           
        } catch(e) {
           console.error('Decoding failed', e);
           alert('テンプレートを正しく取得できませんでした');
        }
        fetch(`/taskle/delete_fields/${encodeURIComponent(selected_Option)}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({selected_Option: decodedSelectedOption})
         })
         .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json(); 
        })
        
        .then(data => {
            document.getElementById("DeleteAdress").value = data.Adress;
            document.getElementById("DeleteMailText").value = data.Mailtext;
            document.getElementById("DeleteTitle").value = data.Subject;
            const todayValue = data.Todays;
            const dt = new Date();

            switch (todayValue) {
                case "option1":
                    deletesubjectText = `${(dt.getMonth() + 1)}月${dt.getDate()}日(${dt.toLocaleDateString('ja-JP', { weekday: 'short' })})`
                    break;
                case "option2":
                    deletesubjectText = `${(dt.getMonth() + 1)}月${dt.getDate()}日`;
                    break;
                case "option3":
                    deletesubjectText = dt.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', weekday: 'short' });
                    break;
                case "option4":
                    deletesubjectText = dt.toLocaleString('ja-JP', { month: 'numeric', day: 'numeric' });
                    break;
                case "option5":
                    deletesubjectText = "";
                    break;
                default:  
                    break;
            }
            document.getElementById("ViewOption").value = deletesubjectText;
        });
    });

    document.getElementById('addtemplate').addEventListener('submit', function(event) {
        event.preventDefault();
 
        const objectiveValue = document.getElementById('AddObjective').value;
        const addressValue = document.getElementById('AddAdress').value;
        const subjectValue = document.getElementById('AddSubject').value;
        const mailTextValue = document.getElementById('AddMailText').value;
        const selectedOption = document.getElementById('AddOption').value;

        if (!objectiveValue || !addressValue || !subjectValue || !mailTextValue) {
            alert('入力情報が不足しています。全ての項目に情報を入力して下さい');
            return;
        }
         

        const emailRegex = /^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$/;
        const emails = addressValue.split(/[;,]/);
        for (const email of emails) {
            const trimmedEmail = email.trim();
            if (!emailRegex.test(trimmedEmail)) {

                alert(`メールアドレスを正しく入力してください: ${trimmedEmail}`);
                return;
            }
        }

        const formData = new FormData();
        formData.append('Objective', objectiveValue);
        formData.append('Adress', addressValue);
        formData.append('Subject', subjectValue);
        formData.append('Mailtext', mailTextValue);
        formData.append('Todays', selectedOption);
        formData.append('DeleteFlag', String(0));
 
        fetch('/taskle/add_template', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Data saved successfully!');
            var selectElement = document.getElementById("AddOption");
            selectElement.selectedIndex = 0;
            alert(data.message);
            location.reload(true);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('テンプレートを追加できませんでした。');
        });
    });
 
    document.getElementById('changetenplate').addEventListener('submit', function(event) {
        event.preventDefault();
        const objectiveValue = document.getElementById('DeleteTemplate').value;
        const addressValue = document.getElementById('DeleteAdress').value;
        const subjectValue = document.getElementById('DeleteTitle').value;
        const mailTextValue = document.getElementById('DeleteMailText').value;
        if ( !addressValue || !subjectValue || !mailTextValue) {
            alert('入力情報が不足しています。全ての項目に情報を入力して下さい');
            return;
        }
        const emailRegex = /^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$/;
        const emails = addressValue.split(/[;,]/);
        for (const email of emails) {
            const trimmedEmail = email.trim();
            if (!emailRegex.test(trimmedEmail)) {

                alert(`メールアドレスを正しく入力してください: ${trimmedEmail}`);
                return;
            }
        }
        const formData = new FormData();
        formData.append('Adress', addressValue);
        formData.append('Subject', subjectValue);
        formData.append('Mailtext', mailTextValue);
        formData.append('Objective', objectiveValue);

        fetch('/taskle/change_template', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Data saved successfully!');
            var selectElement = document.getElementById("AddOption");
            selectElement.selectedIndex = 0;
            alert(data.message);
            location.reload(true);
        })
        .catch(error => {
            console.error('Error:', error);
            alert('テンプレートを変更できませんでした。');
        });
    });
    document.getElementById('deletetenplate').addEventListener('submit', function(event) {
        event.preventDefault();   
        var result = confirm("本当に削除しますか？");
        if (result) {
            const formData = new FormData();
            const objectiveValue = document.getElementById('DeleteTemplate').value;         
            formData.append('Objective', objectiveValue);
            formData.append('DeleteFlag', String(1));
            fetch('/taskle/delete_template', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') 
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('Data saved successfully!');
                var selectElement = document.getElementById("AddOption");
                selectElement.selectedIndex = 0;
                alert(data.message);
                location.reload(true);
            })
            .catch(error => {
                console.error('Error:', error);
                alert('テンプレートを追加できませんでした。');
            });
            console.log("削除しました。");
        } else {
            console.log("削除はキャンセルされました。");
        }
    });
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    } 
    document.getElementById('MailItemForm').addEventListener('submit', function(event) {
        event.preventDefault();
        const inputText = document.getElementById('SendAdress').value;
        const emailRegex = /^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$/;
        const emails = inputText.split(/[;,]/);
        for (const email of emails) {
            const trimmedEmail = email.trim();
            if (!emailRegex.test(trimmedEmail)) {

                alert(`メールアドレスを正しく入力してください: ${trimmedEmail}`);
                return;
            }
        }
        const subject = document.getElementById('SendSubject').value;
        const mailText = document.getElementById('SendMailText').value;

        const outlookURL = `https://outlook.office.com/owa/?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(mailText)}&to=${encodeURIComponent(inputText)}&path=/mail/action/compose`;
        window.open(outlookURL, '_blank');
        location.reload(true);
    });  
    
    const buttons = document.querySelectorAll('.listbutton, .execution-button, .double-execution-button1, .double-execution-button2, .lead-button');
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        button.classList.add('button-pressed');
        setTimeout(function () {
          button.classList.remove('button-pressed');
        }, 100);
      });
    });
});