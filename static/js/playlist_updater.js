let loading=true;

function fetchLiveData() {
	fetch("/get_live_info").then(response => response.json()).then(data => {
		document.getElementById("playlistName").innerHTML = "Musi playlist name: "+data.name;
		if (data.scraped!=data.songs){
			document.getElementById("scraped").innerHTML=data.scraped+"/"+data.songs+" songs loaded from playlist"
			document.getElementById("matched").innerHTML="<br>"
		}
		else{
			document.getElementById("scraped").innerHTML="Musi playlist loaded"
			document.getElementById("matched").innerHTML="Searched for "+data.matched+"/"+data.songs+" songs on Spotify"
		}

		let notFoundTableBody = document.getElementById('notFoundTableBody');
		notFoundTableBody.innerHTML = '';
		if (data.not_found.length>0){
			document.getElementById("notFoundContainer").style.display="block";
		}
		else{
			document.getElementById("notFoundContainer").style.display="none";
		}

		let nf_count=0;
		data.not_found.forEach(song => {
			nf_count+=1;
			let row = document.createElement('tr');

			let Cell = document.createElement('td');
			let CellContainer = document.createElement('p');
			CellContainer.setAttribute("class", "tablecell");
			CellContainer.setAttribute("style", "background-image: url('"+song["thumb"]+"');");
			let Link = document.createElement("a");
			Link.setAttribute("href", song["url"])
			let LinkText = document.createTextNode(song["title"]+" by "+song["artist"]);
			Link.appendChild(LinkText);
			CellContainer.appendChild(Link);
			Cell.appendChild(CellContainer);

			let ButtonCell = document.createElement('td');
			let Button = document.createElement("button");
			Button.addEventListener("click", selectSong, false);
			Button.url=song.url;
			Button.sp_url=""
			let ButtonText = document.createTextNode(nf_count);
			Button.appendChild(ButtonText);
			ButtonCell.appendChild(Button);

			row.appendChild(ButtonCell);
			row.appendChild(Cell);

			notFoundTableBody.appendChild(row);
		});

		let foundTableBody = document.getElementById('foundTableBody');
		foundTableBody.innerHTML = '';

		let m_count=0;
		data.matches.forEach(match => {
			m_count+=1;
			let row = document.createElement('tr');

			let ytCell = document.createElement('td');
			let ytCellContainer = document.createElement('p');
			ytCellContainer.setAttribute("class", "tablecell");
			ytCellContainer.setAttribute("style", "background-image: url('"+match["yt_thumb"]+"');");
			let ytLink = document.createElement("a");
			ytLink.setAttribute("href", match["yt_url"])
			let ytLinkText = document.createTextNode(match["yt_title"]+" by "+match["yt_author"]);
			ytLink.appendChild(ytLinkText);
			ytCellContainer.appendChild(ytLink);
			ytCell.appendChild(ytCellContainer);

			let spCell = document.createElement('td');
			let spCellContainer = document.createElement('p');
			spCellContainer.setAttribute("class", "sptablecell");
			spCellContainer.setAttribute("style", "background-image: url('"+match["sp_thumb"]+"');");
			let spLink = document.createElement("a");
			spLink.setAttribute("href", "http://open.spotify.com/track/"+match["sp_id"])
			let spLinkText = document.createTextNode(match["sp_title"]+" by "+match["sp_artist"]);
			spLink.appendChild(spLinkText);
			spCellContainer.appendChild(spLink);
			spCell.appendChild(spCellContainer);

			let ButtonCell = document.createElement('td');
			let Button = document.createElement("button");
			Button.addEventListener("click", selectSong, false);
			Button.url=match["yt_url"];
			Button.sp_url=spLink.href
			let ButtonText = document.createTextNode(m_count);
			Button.appendChild(ButtonText);
			ButtonCell.appendChild(Button);

			row.appendChild(ButtonCell);
			row.appendChild(ytCell);
			row.appendChild(spCell);

			foundTableBody.appendChild(row);
		});

		loading=data.loading;

		if (data.songs!=0 && data.matched==data.songs){
			document.getElementById("matchUpdater").style.display="block";
			document.getElementById("scraped").innerHTML=""
			document.getElementById("matched").innerHTML="Finished searching for "+data.matched+"/"+data.songs+" songs on Spotify"
			clearInterval(intervalId);
		}
		else if (!loading){
			window.location.replace("/error");
		}
	})
}


function create_playlist(){
	let url=document.getElementById("existingPlaylist").value;
	if (url.startsWith("http://open.spotify.com/playlist/") || url.startsWith("https://open.spotify.com/playlist/") || url.startsWith("open.spotify.com/playlist/")){
		if (url.indexOf("?")>-1){
			url=url.substring(0,url.indexOf("?"));
		}
		console.log(url);
	}
	else if (url!=""){
		alert("Format invalid. Make sure you're copying the correct link!");
		document.getElementById("existingPlaylist").value="";
		return false;
	}
	fetch("/create_playlist", {method:"POST",body: JSON.stringify({url:url})}).then(response => response.json()).then(data => {
		if (data.message=="Success"){
			alert("Successfully converted playlist!");
			window.open(data.link, '_blank').focus();
		}
		else{
			document.getElementById("existingPlaylist").value="";
			alert(data.message);
		}
	});
	return false;
}

function selectSong(event){
	if (loading){
		alert("Please wait for all songs to be searched for. This service only searches spotify once, and after that searches are much faster. If you need to run the search on the playlist a second time, it will not take long, so please wait.");
		return false;
	}
	let yt_url=event.currentTarget.url
	let sp_url=event.currentTarget.sp_url
	fetch("/get_song", {method: "POST", body: JSON.stringify({url:yt_url})}).then(response => response.json()).then(data => {
		document.getElementById("selectedSection").style.display='block';
		document.getElementById("isSelected").innerHTML = "Selected video:";
		document.getElementById("selectedVideo").innerHTML = data.yt_title;
		document.getElementById("selectedVideo").href = yt_url;
		document.getElementById("matchedSong").value = sp_url;
		if (sp_url==""){
			document.getElementById("removeButton").style.display="none";
		}
		else{
			document.getElementById("removeButton").style.display="block";
		}
	});
}

function update_match(){
	let url=document.getElementById("matchedSong").value;
	if (url.startsWith("http://open.spotify.com/track/") || url.startsWith("https://open.spotify.com/track/") || url.startsWith("open.spotify.com/track/")){
		if (url.indexOf("?")>-1){
			url=url.substring(0,url.indexOf("?"));
		}
		console.log(url);
	}
	else if (url!=""){
		alert("Format invalid. Make sure you're copying the correct link!");
		document.getElementById("matchedSong").value="";
		return false;
	}
	else{
		alert("You have to specify a spotify link! If you want to remove this match because the song doesn't exist on spotify, use the \"remove match\" button.");
	}
	let yt_url=document.getElementById("selectedVideo").href;
	fetch("/update_match", {method: "POST", body: JSON.stringify({yt_url:yt_url,sp_url:url,remove:false})}).then(response => response.json()).then(data => {
		console.log(data);
		if (data.message=="Success"){
			fetchLiveData();
			alert("Successfully updated match.");
			cancel_selection();
		}
		else{
			document.getElementById("matchedSong").value="";
			alert(data.message);
		}
	});
	return false;
}

function remove_match(){
	let url=document.getElementById("matchedSong").value;
	if (url.startsWith("http://open.spotify.com/track/") || url.startsWith("https://open.spotify.com/track/") || url.startsWith("open.spotify.com/track/")){
		if (url.indexOf("?")>-1){
			url=url.substring(0,url.indexOf("?"));
		}
		console.log(url);
	}
	else if (url!=""){
		alert("Format invalid. Reselect song.");
		document.getElementById("matchedSong").value="";
		return false;
	}
	let yt_url=document.getElementById("selectedVideo").href;
	fetch("/update_match", {method: "POST", body: JSON.stringify({yt_url:yt_url,sp_url:url,remove:true})}).then(response => response.json()).then(data => {
		console.log(data);
		if (data.message=="Success"){
			fetchLiveData();
			alert("Successfully removed match.");
			cancel_selection();
		}
		else{
			document.getElementById("matchedSong").value="";
			alert(data.message);
		}
	});
	return false;
}

function cancel_selection(){
	document.getElementById("selectedSection").style.display='none';
	document.getElementById("isSelected").innerHTML = "Select a song below by clicking on a number.";
}

var intervalId = window.setInterval(function(){
	fetchLiveData()
}, 1000);