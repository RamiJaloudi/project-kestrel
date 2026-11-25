export default function ResourceShortcut({category,label}:{category:string;label:string}){
 return <p className="resource-shortcut"><a href={'/portal?view=Resources&resourceCategory='+encodeURIComponent(category)}>{label}</a> <small>Fictional examples and field guides</small></p>;
}
