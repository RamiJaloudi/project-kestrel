import logo from './assets/freshfields-square.png';

/** User-supplied visual identity, edited into a square with the wordmark only. */
export default function BrandMark({className=''}:{className?:string}){
 return <img className={'brand-mark '+className} src={logo} alt="FRESHFIELDS" width={128} height={128}/>;
}
